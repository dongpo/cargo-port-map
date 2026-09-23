"""Verify source-to-map conservation without third-party dependencies."""
import collections,json,sqlite3
from pathlib import Path

def validate(db_path='data/sample.sqlite',public='public/data'):
 db=sqlite3.connect(db_path);out=Path(public);m=json.loads((out/'manifest.json').read_text());ports={p['id']:p for p in json.loads((out/'ports.json').read_text())}
 expected=collections.Counter();n=0
 for raw, in db.execute('SELECT raw FROM voyages'):
  v=json.loads(raw);n+=1
  assert v['origin_id']!=v['destination_id'];assert v['departure']<=v['arrival'];assert v['arrival'].startswith(str(m['year']))
  assert all(v[k] is None for k in ('teu','cargo_tonnes','trade_value_usd'))
  expected[(v['month'],v['origin_id'],v['destination_id'])]+=1
 actual=collections.Counter();annual=collections.Counter()
 for month in m['periods']:
  if month=='all':continue
  for e in json.loads((out/f'{month}.json').read_text())['edges']:
   assert e['origin_id'] in ports and e['destination_id'] in ports
   actual[(month,e['origin_id'],e['destination_id'])]+=e['voyage_count'];annual[(e['origin_id'],e['destination_id'])]+=e['voyage_count']
 yearly={(e['origin_id'],e['destination_id']):e['voyage_count'] for e in json.loads((out/'all.json').read_text())['edges']}
 assert actual==expected;assert annual==yearly;assert n==m['voyages']==sum(yearly.values())
 raw_count=db.execute('SELECT count(*) FROM events').fetchone()[0];assert raw_count==m['events']
 print(f'PASS: {raw_count:,} raw events → {n:,} voyages; all monthly/annual aggregates conserve counts; all endpoints resolve.')
if __name__=='__main__':
 import argparse
 ap=argparse.ArgumentParser();ap.add_argument('--db',default='data/sample.sqlite');ap.add_argument('--public',default='public/data');a=ap.parse_args();validate(a.db,a.public)
