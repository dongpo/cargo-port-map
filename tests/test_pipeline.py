import collections,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from pipeline.build import normalize,voyages,build
from pipeline.ingest import connect,put,get,ingest
from pipeline.gfw import next_offset,APIError,params

def event(id='e1',port='p1',start='2025-01-01T00:00:00Z',end='2025-01-02T00:00:00Z',vessel='v1',kind='cargo'):
 return {'id':id,'type':'port_visit','start':start,'end':end,'vessel':{'id':vessel,'type':kind,'ssvid':'test'},'port_visit':{'visitId':id,'intermediateAnchorage':{'id':port,'name':port,'lat':22.5,'lon':120.2,'anchorageId':'a1'}}}
class PipelineTests(unittest.TestCase):
 def derive(self,events):
  q=collections.Counter();r=list(voyages(sorted([normalize(e) for e in events],key=lambda x:(x['vessel_id'],x['arrival'],x['event_id'])),2025,q));return r,q
 def test_directed_cross_year_arrival_month(self):
  r,q=self.derive([event(start='2024-12-28T00:00:00Z',end='2024-12-30T00:00:00Z'),event('e2','p2','2025-01-01T00:00:00Z','2025-01-02T00:00:00Z')]);self.assertEqual(len(r),1);self.assertEqual(r[0]['month'],'2025-01');self.assertEqual(r[0]['origin_id'],'p1');self.assertIsNone(r[0]['teu'])
 def test_same_port_latest_departure(self):
  r,q=self.derive([event(),event('e2','p1','2025-01-03T00:00:00Z','2025-01-05T00:00:00Z'),event('e3','p2','2025-02-01T00:00:00Z','2025-02-02T00:00:00Z')]);self.assertEqual(len(r),1);self.assertTrue(r[0]['departure'].startswith('2025-01-05'));self.assertEqual(q['same_port_collapsed'],1)
 def test_non_cargo_and_unknown_port_break_sequence(self):
  for mid in [event('e2',None,'2025-01-03T00:00:00Z','2025-01-04T00:00:00Z'),event('e2','p2','2025-01-03T00:00:00Z','2025-01-04T00:00:00Z',kind='fishing')]:
   r,q=self.derive([event(),mid,event('e3','p3','2025-01-06T00:00:00Z','2025-01-07T00:00:00Z')]);self.assertEqual(r,[])
 def test_overlap_and_vessel_isolation(self):
  r,q=self.derive([event(end='2025-01-10T00:00:00Z'),event('e2','p2','2025-01-03T00:00:00Z','2025-01-04T00:00:00Z'),event('e3','p3','2025-01-06T00:00:00Z','2025-01-07T00:00:00Z'),event('e4','p4',vessel='v2')]);self.assertEqual(r,[]);self.assertEqual(q['overlapping_distinct_ports'],1)
 def test_gap_limit(self):
  r,q=self.derive([event(),event('e2','p2','2025-11-01T00:00:00Z','2025-11-02T00:00:00Z')]);self.assertFalse(r);self.assertEqual(q['gap_over_limit'],1)
 def test_timezone_and_coordinates(self):
  e=event(start='2025-02-01T01:00:00+08:00',end='2025-02-02T01:00:00+08:00');self.assertTrue(normalize(e)['arrival'].startswith('2025-01-31'));e['port_visit']['intermediateAnchorage']['lat']=float('nan');self.assertEqual(normalize(e)['rejection'],'invalid_coordinates')
 def test_pagination_stall(self):
  with self.assertRaises(APIError):next_offset({'entries':[],'total':3,'nextOffset':0},0)
  self.assertIsNone(next_offset({'entries':[1],'total':1,'nextOffset':1},0))
 def test_live_query_spelling(self):
  p=params('2025-01-01','2026-01-01');self.assertEqual(p['vessel-types[0]'],'CARGO');self.assertEqual(p['sort'],'+start');self.assertNotIn('vesselTypes',p)
 def test_resume_dedup_and_aggregation(self):
  with tempfile.TemporaryDirectory() as temp:
   db=connect(Path(temp)/'test.sqlite');put(db,'config',{'year':2025,'sample_vessels':0});db.commit()
   a=event();b=event('e2','p2','2025-01-05T00:00:00Z','2025-01-06T00:00:00Z')
   with patch('pipeline.ingest.request',side_effect=[{'entries':[a],'total':2,'nextOffset':1},APIError('interrupted')]):
    with self.assertRaises(APIError):ingest(db,{},'batch-0')
   self.assertEqual(get(db,'batch-0'),1)
   with patch('pipeline.ingest.request',return_value={'entries':[b],'total':2,'nextOffset':2}):ingest(db,{},'batch-0')
   self.assertEqual(db.execute('SELECT count(*) FROM events').fetchone()[0],2)
   with self.assertRaises(ValueError):build(Path(temp)/'test.sqlite',Path(temp)/'out')
   put(db,'complete',True);db.commit()
   m=build(Path(temp)/'test.sqlite',Path(temp)/'out');self.assertEqual(m['voyages'],1)
   annual=json.loads((Path(temp)/'out/all.json').read_text());self.assertEqual(sum(x['voyage_count'] for x in annual['edges']),1)
   m2=build(Path(temp)/'test.sqlite',Path(temp)/'out');self.assertEqual(m2['voyages'],1)
if __name__=='__main__':unittest.main()
