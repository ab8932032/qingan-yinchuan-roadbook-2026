from pathlib import Path
from html.parser import HTMLParser
import json
import re
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'index.html').read_text(encoding='utf-8')
JS=(ROOT/'scripts/atlas.js').read_text(encoding='utf-8')
SW=(ROOT/'service-worker.js').read_text(encoding='utf-8')
DATA=json.loads((ROOT/'scripts/atlas-data.js').read_text(encoding='utf-8').removeprefix('window.ROADBOOK = ').rstrip(';\n'))
PLACES={p['id']:p for p in DATA['places']}

class Structure(HTMLParser):
 def __init__(self):
  super().__init__();self.ids=[];self.assets=[];self.links=[]
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if a.get('id'):self.ids.append(a['id'])
  if tag=='script' and a.get('src'):self.assets.append(a['src'])
  if tag=='img' and a.get('src'):self.assets.append(a['src'])
  if tag=='link' and a.get('href'):self.assets.append(a['href'])
  if tag=='a' and a.get('href'):self.links.append(a['href'])

class AtlasContentTests(unittest.TestCase):
 def test_route_is_complete_and_returns_through_the_real_stops(self):
  self.assertEqual(len(PLACES),21)
  self.assertEqual(len(PLACES),len(DATA['places']))
  self.assertEqual(set(DATA['route']),{p['id'] for p in PLACES.values() if not p.get('parent')})
  self.assertEqual(DATA['route'][0], 'chengdu')
  self.assertEqual(DATA['route'][-2:], ['xining','chengdu'])
  i=DATA['route'].index('pingshanhu')
  self.assertEqual(DATA['route'][i:i+3], ['pingshanhu','zhangye','danxia'])
  i=DATA['route'].index('lenghu')
  self.assertEqual(DATA['route'][i:i+6], ['lenghu','oil-town','heidu','mars','water','chaerhan'])

 def test_actual_salt_lake_overnight_and_gate_visit_are_preserved(self):
  self.assertIn('察尔汗',PLACES['chaerhan']['name'])
  self.assertIn('当晚住在德令哈', ''.join(PLACES['chaerhan']['memory']))
  self.assertIn('46 元',''.join(PLACES['dunhuang']['memory']))
  self.assertEqual(PLACES['mars']['status'],'门口停留')
  actual=''.join(''.join(p['memory']) for p in PLACES.values())
  for old in ['大柴旦希岸','已订','原订 2500','下午完整游翡翠湖']:
   self.assertNotIn(old,actual)
  self.assertIn(['23 点多','到附近拍星空'],PLACES['lake']['timeline'])
  self.assertIn('清晨 7 点',''.join(PLACES['chengdu']['memory']))

 def test_each_location_has_a_model_a_record_and_valid_legacy_dates(self):
  s=Structure();s.feed(HTML)
  self.assertEqual(len(s.ids),len(set(s.ids)))
  self.assertIn(DATA['defaultPlace'],PLACES)
  for p in PLACES.values():
   self.assertTrue(p['memory'])
   self.assertIn('model-'+p['kind'],s.ids)
   self.assertIn('record-'+p['id'],s.ids)
   self.assertGreaterEqual(p['x'],0);self.assertLessEqual(p['x'],DATA['width'])
   self.assertGreaterEqual(p['y'],0);self.assertLessEqual(p['y'],DATA['height'])
   for day in p.get('legacyDays',[]):self.assertRegex(day,r'^d\d{3,4}$')
  for alias,place in DATA['legacyAliases'].items():self.assertIn(place,PLACES)

 def test_local_assets_and_backup_are_in_the_offline_shell(self):
  s=Structure();s.feed(HTML)
  for asset in s.assets:
   self.assertFalse(asset.startswith(('http:','https:')))
   self.assertTrue((ROOT/asset.split("?",1)[0]).is_file(),asset)
   self.assertIn('"./'+asset+'"',SW)
  self.assertNotIn('roadbook-original.html',s.links)
  self.assertIn('libraryDialog',s.ids)
  self.assertIn('"./roadbook-original.html"',SW)
  original=(ROOT/'roadbook-original.html').read_text(encoding='utf-8')
  for section in ['days','spots','route','budget','todo','return']:
   self.assertIn('id="'+section+'"',original)
  self.assertIn('房舍与庭院',original)

 def test_stories_are_attached_to_visited_places(self):
  self.assertGreater(sum(len(p.get('story',[])) for p in PLACES.values()),55)
  self.assertEqual(PLACES['danxia']['storyTitle'],'七彩丹霞')
  self.assertTrue(PLACES['lake']['sources'])
  self.assertEqual(PLACES['siju']['parent'],'dunhuang')
  self.assertEqual(PLACES['dunhuang']['branches'],['nightmarket','siju'])
  # Ambiguous names stay as supplied; the oil town is not silently identified as another site.
  self.assertNotIn('story',PLACES['oil-town'])

 def test_browser_storage_contract_is_non_destructive(self):
  self.assertIn('`roadbook-place:${id}:note`',JS)
  self.assertIn('`roadbook-note:${day}:line`',JS)
  self.assertIn('`roadbook-note:${day}:timing`',JS)
  self.assertIn('indexedDB.open("qinggan-roadbook-media", 1)',JS)
  self.assertIn('db.transaction("media", "readonly")',JS)
  for destructive in ['localStorage.clear','deleteDatabase','deleteObjectStore']:
   self.assertNotIn(destructive,JS)

 def test_no_script_fallback_contains_each_location_and_memory(self):
  fallback=HTML.split('<noscript>',1)[1].split('</noscript>',1)[0]
  for p in PLACES.values():
   self.assertIn('id="record-'+p['id']+'"',fallback)
   self.assertIn(p['name'],fallback)

 def test_runtime_scripts_parse(self):
  for file in ['scripts/atlas-data.js','scripts/atlas.js','scripts/theater-data.js','scripts/theater.js','scripts/journey-archive.js','scripts/journey-plan.js','service-worker.js']:
   subprocess.run(['node','--check',str(ROOT/file)],check=True,capture_output=True)

class OfflineUpdateTests(unittest.TestCase):
 def test_updated_core_asset_wins_and_offline_asset_never_receives_html(self):
  harness=r'''
const fs=require('fs'),vm=require('vm');
const buckets=new Map();
const bucket=(name)=>{
 if(!buckets.has(name))buckets.set(name,new Map());
 const entries=buckets.get(name);
 return {match:async(key)=>entries.get(String(key))?.clone(),put:async(key,value)=>entries.set(String(key),value.clone())};
};
const cache={open:async(name)=>bucket(name),match:async(key)=>{
 for(const name of buckets.keys()){const hit=await bucket(name).match(key);if(hit)return hit;}
}};
const context={Response,URL,Promise,caches:cache,fetch:async()=>new Response('new script'),self:{addEventListener(){}}};
vm.createContext(context);
vm.runInContext(fs.readFileSync(process.argv[1],'utf8')+'\nglobalThis.testFns={networkFirstAsset,staleWhileRevalidate,CORE_CACHE,RUNTIME_CACHE};',context);
(async()=>{
 const {networkFirstAsset,staleWhileRevalidate,CORE_CACHE,RUNTIME_CACHE}=context.testFns;
 await bucket(CORE_CACHE).put('script',new Response('old script'));
 const online=await(await networkFirstAsset('script')).text();
 context.fetch=async()=>{throw Error('offline');};
 const offline=await(await networkFirstAsset('script')).text();
 await bucket(CORE_CACHE).put('./index.html',new Response('<html>book</html>'));
 const missing=await networkFirstAsset('missing.js');
 await bucket(CORE_CACHE).put('style',new Response('old style'));
 await bucket(RUNTIME_CACHE).put('style',new Response('new style'));
 const updated=await(await staleWhileRevalidate('style')).text();
 process.stdout.write(JSON.stringify({online,offline,missing:missing.status,updated}));
})().catch(e=>{process.stderr.write(e.stack);process.exit(1)});
'''
  result=subprocess.run(['node','-e',harness,str(ROOT/'service-worker.js')],capture_output=True,text=True,encoding='utf-8',check=True)
  self.assertEqual(json.loads(result.stdout),{'online':'new script','offline':'new script','missing':504,'updated':'new style'})

if __name__=='__main__':unittest.main()
