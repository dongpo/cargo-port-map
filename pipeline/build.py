"""Normalize -> sequence -> directed voyages -> monthly/year aggregates (UTC)."""
import argparse, collections, gzip, json, math, sqlite3, hashlib
from pathlib import Path
from datetime import datetime, timezone
from .ingest import connect,get
from .gfw import DATASET

def stamp(value):
    d=datetime.fromisoformat(value.replace('Z','+00:00'))
    if d.tzinfo is None: raise ValueError('Timezone required')
    return d.astimezone(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00','Z')

def normalize(e):
    v=e.get('vessel') or {}; pv=e.get('port_visit') or {}; a=pv.get('intermediateAnchorage') or {}
    if not v.get('id'): raise ValueError('Missing vessel ID')
    start=stamp(e['start']);end=stamp(e['end'])
    reason=None
    if e.get('type')!='port_visit': reason='not_port_visit'
    elif str(v.get('type','')).upper()!='CARGO': reason='not_cargo'
    elif end<start: reason='invalid_interval'
    elif not a.get('id'): reason='missing_port'
    try:
        lon=float(a['lon']);lat=float(a['lat'])
        if not math.isfinite(lon+lat) or not -180<=lon<=180 or not -90<=lat<=90: raise ValueError()
    except (KeyError,ValueError,TypeError): lon=lat=None;reason=reason or 'invalid_coordinates'
    return {'event_id':e['id'],'visit_id':pv.get('visitId'),'vessel_id':v['id'],'ssvid':v.get('ssvid'),
        'vessel_type':str(v.get('type','')).upper(),'port_id':a.get('id'),'port_name':a.get('name'),
        'port_flag':a.get('flag'),'anchorage_id':a.get('anchorageId'),'longitude':lon,'latitude':lat,
        'arrival':start,'departure':end,'confidence':pv.get('confidence'),'rejection':reason,
        'provenance':{'provider':'Global Fishing Watch','dataset':DATASET,'source_event_id':e['id']}}

def voyages(rows,year,quality,max_gap_days=90):
    previous=None;vessel=None;blocked_until=None
    for r in rows:
        if r['vessel_id']!=vessel: previous=None;vessel=r['vessel_id'];blocked_until=None
        if blocked_until and r['arrival']<blocked_until:
            quality['inside_ambiguous_interval']+=1
            blocked_until=max(blocked_until,r.get('departure',blocked_until));continue
        if r['rejection']:
            quality[r['rejection']]+=1;previous=None;continue
        if previous is None: previous=r;continue
        if r['port_id']==previous['port_id']:
            quality['same_port_collapsed']+=1
            # Keep arrival from the earliest visit; departure and provenance from the latest-ending visit.
            if r['departure']>previous['departure']:
                previous={**r,'arrival':previous['arrival']}
            continue
        gap=(datetime.fromisoformat(r['arrival'].replace('Z','+00:00'))-datetime.fromisoformat(previous['departure'].replace('Z','+00:00'))).total_seconds()/86400
        if gap<0:
            quality['overlapping_distinct_ports']+=1
            # Both records are ambiguous. Neither can bridge to the next port.
            blocked_until=max(previous['departure'],r['departure']);previous=None;continue
        if gap>max_gap_days:
            quality['gap_over_limit']+=1;previous=r;continue
        if int(r['arrival'][:4])==year:
            key=previous['event_id']+'>'+r['event_id']
            yield {'voyage_id':hashlib.sha256(key.encode()).hexdigest()[:24],
                'vessel_id':vessel,'ssvid':r['ssvid'],'origin_id':previous['port_id'],'destination_id':r['port_id'],
                'origin_arrival':previous['arrival'],'departure':previous['departure'],
                'arrival':r['arrival'],'destination_departure':r['departure'],
                'origin_event_id':previous['event_id'],'destination_event_id':r['event_id'],
                'year':year,'month':r['arrival'][:7],'voyage_count':1,
                'teu':None,'cargo_tonnes':None,'trade_value_usd':None,
                'provenance':{'provider':'Global Fishing Watch','dataset':DATASET,'method':'consecutive_distinct_port_visits'}}
        previous=r

def write_json(path,value):
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(value,separators=(',',':'),allow_nan=False));temp.replace(path)

def build(db_path,output,max_gap_days=90):
    db=connect(db_path)
    if not get(db,'complete',False): raise ValueError('Ingestion incomplete; refusing to publish misleading aggregates. Resume ingestion first.')
    config=get(db,'config');year=config['year'];quality=collections.Counter();ports={}
    db.executescript('DROP TABLE IF EXISTS visits; CREATE TABLE visits(event_id TEXT PRIMARY KEY,vessel TEXT,arrival TEXT,raw TEXT); DROP TABLE IF EXISTS voyages; CREATE TABLE voyages(id TEXT PRIMARY KEY,raw TEXT);')
    for (raw,) in db.execute('SELECT raw FROM events ORDER BY id'):
        e=json.loads(raw)
        try:r=normalize(e)
        except (ValueError,KeyError,TypeError):
            # An unorderable event means we cannot safely reconstruct this vessel's sequence.
            quality['unorderable_events']+=1
            v=(e.get('vessel') or {}).get('id')
            if not v: raise ValueError('Event without vessel ID; cannot safely sequence data')
            r={'event_id':e['id'],'vessel_id':v,'arrival':'','rejection':'unorderable'}
        db.execute('INSERT INTO visits VALUES(?,?,?,?)',(r['event_id'],r['vessel_id'],r['arrival'],json.dumps(r)))
        if not r.get('rejection'):
            # Source coordinates remain exact in visits; map uses a deterministic source representative.
            ports.setdefault(r['port_id'],{'id':r['port_id'],'name':r['port_name'],'flag':r['port_flag'],'longitude':r['longitude'],'latitude':r['latitude'],'anchorage_id':r['anchorage_id']})
    db.execute('CREATE INDEX visits_sequence ON visits(vessel,arrival,event_id)')
    bad={r[0] for r in db.execute("SELECT DISTINCT vessel FROM visits WHERE arrival=''")}
    counts=collections.Counter();vessel_ids=set();total=0
    rows=(json.loads(r[0]) for r in db.execute('SELECT raw FROM visits ORDER BY vessel,arrival,event_id') if json.loads(r[0])['vessel_id'] not in bad)
    for v in voyages(rows,year,quality,max_gap_days):
        db.execute('INSERT INTO voyages VALUES(?,?)',(v['voyage_id'],json.dumps(v)))
        counts[(v['month'],v['origin_id'],v['destination_id'])]+=1
        vessel_ids.add(v['vessel_id']);total+=1
    db.commit();quality['excluded_unorderable_vessels']=len(bad)
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    annual=collections.Counter()
    def edge(o,d,n):return {'origin_id':o,'destination_id':d,'voyage_count':n,'teu':None,'cargo_tonnes':None,'trade_value_usd':None}
    periods={f'{year}-{m:02}':[] for m in range(1,13)}
    for (month,o,d),n in sorted(counts.items()):periods[month].append(edge(o,d,n));annual[(o,d)]+=n
    periods['all']=[edge(o,d,n) for (o,d),n in sorted(annual.items())]
    for period,edges in periods.items():write_json(output/f'{period}.json',{'period':period,'edges':edges})
    write_json(output/'ports.json',list(sorted(ports.values(),key=lambda p:p['id'])))
    cohort=get(db,'cohort')
    manifest={'schema_version':'0.1.0','year':year,'dataset':DATASET,'provider':'Global Fishing Watch',
        'coverage':'live vessel cohort' if cohort else 'global query','is_sample':bool(cohort),
        'cohort_vessels':len(cohort) if cohort else None,'vessels_with_voyages':len(vessel_ids),
        'events':db.execute('SELECT count(*) FROM events').fetchone()[0],'ports':len(ports),'voyages':total,
        'directed_connections':len(annual),'retrieved_at':get(db,'retrieved_at'),'ingestion_complete':True,
        'window':get(db,'window'),'periods':['all']+list(periods)[:-1],
        'month_assignment':'destination arrival UTC','metric':'observed vessel voyages; not trade',
        'geometry':'great-circle OD connectors, not sailed tracks','max_gap_days':max_gap_days,
        'sample_method':f'Up to {config["sample_vessels"]} unique cargo vessels from eight evenly spaced offsets in start-sorted 2025 events; complete padded-window histories for the selected cohort. Non-random, not representative.' if cohort else None,
        'quality':dict(quality),'boundary_caveat':'One month of padding; arrivals whose predecessor lies outside the window are censored.'}
    write_json(output/'manifest.json',manifest)
    for table in ('visits','voyages'):
        with gzip.open(Path(db_path).parent/f'{table}.jsonl.gz','wt') as f:
            for (raw,) in db.execute(f'SELECT raw FROM {table}'):f.write(raw+'\n')
    print(json.dumps(manifest,indent=2));return manifest
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--db',default='data/gfw.sqlite');ap.add_argument('--output',default='public/data');ap.add_argument('--max-gap-days',type=float,default=90);a=ap.parse_args()
    build(a.db,a.output,a.max_gap_days)
