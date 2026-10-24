from pathlib import Path
import json
import unittest

ROOT=Path(__file__).resolve().parents[1]
def js_data(file,prefix):
 return json.loads((ROOT/file).read_text(encoding='utf-8').removeprefix(prefix).rstrip(';\n'))
ATLAS=js_data('scripts/atlas-data.js','window.ROADBOOK = ')
PLAN=js_data('scripts/journey-plan.js','window.JOURNEY_PLAN = ')
SOURCE=json.loads((ROOT/'notes/amap-route-reference-2026-10-24.json').read_text(encoding='utf-8'))

class JourneyPlanTests(unittest.TestCase):
 def test_days_legs_and_guides_follow_the_actual_route(self):
  places={p['id'] for p in ATLAS['places']}
  self.assertEqual([(l['fr'],l['to']) for l in PLAN['legs']],list(zip(ATLAS['route'],ATLAS['route'][1:])))
  self.assertEqual(set(PLAN['guides']),places)
  self.assertEqual(len(PLAN['days']),12)
  for day in PLAN['days']:
   for step in day['steps']:self.assertIn(step['place'],places)
  self.assertIn('siju',places)
  self.assertIn('nightmarket',places)
  self.assertEqual(ATLAS['placeAliases'],{'ebol':'mars'})

 def test_amap_reference_is_traceable_and_preserves_the_one_hour_measurement(self):
  routes={(r['fr'],r['to']):r for r in SOURCE['routes']}
  mapped=0
  for leg in PLAN['legs']:
   if 'amap' not in leg:continue
   mapped+=1
   key=(leg['fr'],leg['to'])
   if key==('mingsha','lenghu'):key=('dunhuang','lenghu')
   route=routes[key]
   self.assertEqual(leg['amap']['time'],route['time'])
   self.assertEqual(leg['amap']['distance'],route['distance'])
   self.assertGreater(route['time'],0)
   self.assertGreater(route['distance'],0)
   self.assertIn('uri.amap.com/navigation?',route['url'])
   self.assertEqual(route['queriedAt'],'2026-10-24')
  self.assertEqual(mapped,18)
  measured=next(l for l in PLAN['legs'] if (l['fr'],l['to'])==('zhangye','pingshanhu'))
  self.assertEqual(measured['duration'],'1 小时')
  self.assertEqual(measured['basis'],'实测时间')
  self.assertIn('高德',measured['reference'])

 def test_ambiguous_camp_is_not_given_a_false_location_or_duration(self):
  for leg in PLAN['legs']:
   if 'camp' in (leg['fr'],leg['to']):
    self.assertNotIn('amap',leg)
    self.assertEqual(leg['basis'],'位置待补')
  daily=next(d for d in PLAN['days'] if d['date']=='10.1')
  keys=[('dunhuang','lenghu'),('lenghu','oil-town'),('oil-town','heidu'),('heidu','mars'),('mars','water')]
  routes={(r['fr'],r['to']):r for r in SOURCE['routes']}
  self.assertEqual(sum(routes[k]['time'] for k in keys),29763)
  self.assertIn('8 小时 15 分钟',daily['drivingReference']['duration'])

 def test_city_prefixes_and_road_labels_keep_separate_stations(self):
  places={p['id']:p for p in ATLAS['places']}
  for id,city in [('pingshanhu','张掖'),('danxia','张掖'),('mingsha','敦煌'),('heidu','冷湖'),('mars','冷湖')]:
   self.assertTrue(places[id]['name'].startswith(city+' · '))
  self.assertNotIn('ebol',places)
  self.assertNotIn('ebol',ATLAS['route'])
  self.assertNotIn('City Walk',places['dunhuang']['name'])
  self.assertEqual(places['mars']['road'],'火星一号公路')
  self.assertTrue(any(l['text']=='火星一号公路' for l in ATLAS['roadLabels']))
  leg=next(l for l in PLAN['legs'] if (l['fr'],l['to'])==('heidu','mars'))
  self.assertIn('S316',leg['note'])
  self.assertIn('不能等同火星一号公路',SOURCE['notes'][-1])

 def test_dunhuang_branches_have_records_without_fabricated_driving_legs(self):
  places={p['id']:p for p in ATLAS['places']}
  self.assertEqual(places['dunhuang']['name'],'敦煌')
  self.assertEqual(set(places['dunhuang']['branches']),{'siju','nightmarket'})
  for id in ['siju','nightmarket']:
   self.assertEqual(places[id]['parent'],'dunhuang')
   self.assertNotIn(id,ATLAS['route'])
   self.assertNotIn(id,ATLAS['placeAliases'])
   self.assertFalse(any(id in (l['fr'],l['to']) for l in PLAN['legs']))
  day=next(d for d in PLAN['days'] if d['date']=='9.29')
  self.assertEqual({s['place'] for s in day['steps']},{'siju','nightmarket'})
