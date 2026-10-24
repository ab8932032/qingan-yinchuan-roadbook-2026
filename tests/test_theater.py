from pathlib import Path
import json
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
THEATER = json.loads((ROOT / 'scripts/theater-data.js').read_text(encoding='utf-8').removeprefix('window.ROADBOOK_THEATER = ').rstrip(';\n'))
ATLAS = json.loads((ROOT / 'scripts/atlas-data.js').read_text(encoding='utf-8').removeprefix('window.ROADBOOK = ').rstrip(';\n'))


class TheaterTests(unittest.TestCase):
    def test_six_acts_cover_the_actual_places(self):
        places = {p['id'] for p in ATLAS['places']}
        self.assertEqual(len(THEATER['acts']), 6)
        self.assertEqual(len({a['id'] for a in THEATER['acts']}), 6)
        covered = set()
        for act in THEATER['acts']:
            self.assertIn(act['hero'], act['places'])
            self.assertTrue(set(act['places']) <= places)
            self.assertIsInstance(act['media'], list)
            self.assertTrue(act['shots'])
            covered.update(act['places'])
        self.assertEqual(covered, places)
        self.assertEqual(set(THEATER['layout']), places)

    def test_the_media_helpers_keep_real_assets_and_safe_timing(self):
        harness = r'''
const fs=require('fs'),vm=require('vm');
const context={window:{}};
vm.createContext(context);vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),context);
const util=context.window.RoadbookFilm;
const items=util.normalizeClips([
 {type:'photo',src:'media/院子.jpg',duration:0,caption:'<真实文字>'},
 {type:'photo',src:'media/photo.jpg',duration:120},
 {type:'video',src:'media/film.mp4',start:2,duration:6,poster:'javascript:bad'},
 {type:'video',src:'media/film2.mp4',start:3,end:9},
 {type:'video',src:'javascript:bad'},
 {type:'photo',src:'data:image/png;base64,abc'},
 {type:'unknown',src:'media/other.bin'},null
]);
process.stdout.write(JSON.stringify({items,sources:[util.safeSource('file:///secret'),util.safeSource('https://example.com/movie.mp4'),util.safeSource('blob:https://example.com/clip')]}));
'''
        result = subprocess.run(['node', '-e', harness, str(ROOT / 'scripts/theater.js')], capture_output=True, text=True, encoding='utf-8', check=True)
        data = json.loads(result.stdout)
        self.assertEqual(len(data['items']), 4)
        self.assertEqual(data['items'][0]['duration'], 4)
        self.assertEqual(data['items'][0]['caption'], '<真实文字>')
        self.assertEqual(data['items'][1]['duration'], 60)
        self.assertEqual((data['items'][2]['start'], data['items'][2]['end']), (2, 8))
        self.assertEqual(data['items'][2]['poster'], '')
        self.assertEqual(data['items'][3]['end'], 9)
        self.assertEqual(data['sources'], ['', 'https://example.com/movie.mp4', 'blob:https://example.com/clip'])

    def test_empty_media_slots_do_not_reference_fake_footage(self):
        for act in THEATER['acts']:
            for clip in act['media']:
                self.assertIn(clip['type'], ['video', 'photo'])
                self.assertTrue(clip.get('src'))
                if not clip['src'].startswith(('https:', 'http:', 'blob:')):
                    self.assertTrue((ROOT / clip['src']).is_file())
        html = (ROOT / 'index.html').read_text(encoding='utf-8')
        self.assertIn('id="paperCinema"', html)
        self.assertIn('id="journeyMedia"', html)
        for removed in ['cinemaDialog','展开这一站','看这一幕','影像留白','纸片预演','第一幕']:
            self.assertNotIn(removed, html)

    def test_daily_films_cover_the_journey_and_both_screen_orientations(self):
        plan = json.loads((ROOT/'scripts/journey-plan.js').read_text(encoding='utf-8').removeprefix('window.JOURNEY_PLAN = ').rstrip(';\n'))
        films = THEATER['dailyFilms']
        self.assertEqual({f['date'] for f in films},{d['date'] for d in plan['days']})
        self.assertEqual(len(films),12)
        places = {p['id'] for p in ATLAS['places']}
        self.assertEqual(set().union(*(set(f['places']) for f in films)),places)
        for film in films:
            self.assertTrue(set(film['places']) <= places)
            for clip in film['media']:
                self.assertEqual(clip['type'],'video')
                for key in ['src','portraitSrc','poster','portraitPoster']:
                    self.assertTrue((ROOT/clip[key]).is_file(),clip[key])
                    self.assertGreater((ROOT/clip[key]).stat().st_size,1000)

    def test_cached_full_video_can_supply_offline_byte_ranges(self):
        harness = r'''
const fs=require('fs'),vm=require('vm');
const rows=new Map();let fetches=0;
const cache={match:async key=>rows.get(key)?.clone(),put:async(key,res)=>rows.set(key,res.clone())};
const context={Response,URL,Promise,Number,caches:{open:async()=>cache},fetch:async()=>{fetches++;return new Response('0123456789',{headers:{'Content-Type':'video/mp4'}})},self:{addEventListener(){}}};
vm.createContext(context);vm.runInContext(fs.readFileSync(process.argv[1],'utf8')+'\nglobalThis.readFilm=filmWithRange;',context);
const req=range=>({url:'http://local/media/films/day.mp4',headers:new Headers(range?{range}:{})});
(async()=>{
 const first=await context.readFilm(req('bytes=2-5'));
 const a={status:first.status,text:await first.text(),range:first.headers.get('Content-Range')};
 context.fetch=async()=>{throw Error('offline')};
 const suffix=await context.readFilm(req('bytes=-3'));
 const invalid=await context.readFilm(req('bytes=30-'));
 const all=await context.readFilm(req());
 process.stdout.write(JSON.stringify({a,suffix:await suffix.text(),invalid:invalid.status,all:await all.text(),fetches,cached:await rows.values().next().value.clone().text()}));
})().catch(e=>{console.error(e);process.exitCode=1});
'''
        result=subprocess.run(['node','-e',harness,str(ROOT/'service-worker.js')],capture_output=True,text=True,check=True)
        data=json.loads(result.stdout)
        self.assertEqual(data['a'],{'status':206,'text':'2345','range':'bytes 2-5/10'})
        self.assertEqual(data['suffix'],'789')
        self.assertEqual(data['invalid'],416)
        self.assertEqual(data['all'],'0123456789')
        self.assertEqual(data['cached'],'0123456789')
        self.assertEqual(data['fetches'],1)


if __name__ == '__main__':
    unittest.main()
