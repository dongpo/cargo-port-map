"""Resumable raw ingestion. Run from project root with python3 -m pipeline.ingest."""
import argparse, json, sqlite3, hashlib
from pathlib import Path
from datetime import datetime, timezone
from .gfw import request, params, next_offset, DATASET, APIError

def connect(path):
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(path)
    db.executescript('''PRAGMA journal_mode=WAL;
    CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY, raw TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS state(key TEXT PRIMARY KEY, value TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS pages(query_key TEXT, offset INTEGER, total INTEGER, fetched_at TEXT, digest TEXT, PRIMARY KEY(query_key,offset));''')
    return db

def get(db,key,default=None):
    row=db.execute('SELECT value FROM state WHERE key=?',(key,)).fetchone()
    return json.loads(row[0]) if row else default

def put(db,key,value): db.execute('INSERT OR REPLACE INTO state VALUES(?,?)',(key,json.dumps(value)))

def ingest(db, p, key):
    offset=get(db,key,0)
    while offset is not None:
        p['offset']=offset
        page=request(p)
        raw=json.dumps(page,sort_keys=True)
        for e in page['entries']:
            if not e.get('id') or e.get('type') != 'port_visit': raise APIError('Unexpected event identity/type')
            db.execute('INSERT OR IGNORE INTO events VALUES(?,?)',(e['id'],json.dumps(e)))
        nxt=next_offset(page,offset)
        db.execute('INSERT OR REPLACE INTO pages VALUES(?,?,?,?,?)',(key,offset,page['total'],datetime.now(timezone.utc).isoformat(),hashlib.sha256(raw.encode()).hexdigest()))
        put(db,key,nxt);db.commit()
        print(f'{key}: {min(offset+len(page["entries"]),page["total"]):,}/{page["total"]:,} events',flush=True)
        offset=nxt

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--year',type=int,default=2025)
    ap.add_argument('--sample-vessels',type=int,default=0,help='0 = full global ingestion; otherwise a deterministic discovery cohort')
    ap.add_argument('--db',default='data/gfw.sqlite')
    ap.add_argument('--page-size',type=int,default=1000)
    args=ap.parse_args()
    if args.sample_vessels<0 or not 1<=args.page_size<=10000: ap.error('Invalid sample/page size')
    db=connect(args.db)
    config={'year':args.year,'sample_vessels':args.sample_vessels,'dataset':DATASET}
    old=get(db,'config')
    if old and old!=config: raise APIError('Use a separate database for a different ingestion scope.')
    put(db,'config',config);put(db,'complete',False);db.commit()
    # Padding reduces boundary censoring; voyages are assigned by destination arrival in build.
    start=f'{args.year-1}-12-01';end=f'{args.year+1}-02-01'
    cohort=get(db,'cohort')
    if args.sample_vessels and cohort is None:
        probe=request(params(f'{args.year}-01-01',f'{args.year+1}-01-01',limit=1))
        total=probe['total'];cohort=[]
        for n in range(8):
            offset=int((total-1)*n/8)
            page=request(params(f'{args.year}-01-01',f'{args.year+1}-01-01',offset=offset,limit=max(20,args.sample_vessels//8)))
            for e in page['entries']:
                v=e.get('vessel',{})
                if str(v.get('type','')).upper()=='CARGO' and v.get('id') not in cohort: cohort.append(v['id'])
        cohort=cohort[:args.sample_vessels]
        if not cohort: raise APIError('No cargo vessels discovered')
        put(db,'cohort',cohort);put(db,'discovery_total',total);db.commit()
    batches=[cohort[i:i+20] for i in range(0,len(cohort),20)] if cohort else [()]
    for i,batch in enumerate(batches):
        ingest(db,params(start,end,limit=args.page_size,vessels=batch),f'batch-{i}')
    put(db,'complete',True);put(db,'retrieved_at',datetime.now(timezone.utc).isoformat());put(db,'window',{'start':start,'end':end});db.commit()
    print('Ingestion complete; build with python3 -m pipeline.build --db '+args.db)
if __name__=='__main__':
    try: main()
    except APIError as e: raise SystemExit(str(e))
