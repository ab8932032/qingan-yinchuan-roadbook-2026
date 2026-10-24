from pathlib import Path
from bs4 import BeautifulSoup
import json

root = Path(__file__).resolve().parents[1]
source = BeautifulSoup((root / 'roadbook-original.html').read_text(encoding='utf-8'), 'html.parser')
atlas = json.loads((root / 'scripts/atlas-data.js').read_text(encoding='utf-8').removeprefix('window.ROADBOOK = ').rstrip(';\n'))
allowed = {'p','h3','h4','ul','ol','li','dl','dt','dd','details','summary','table','thead','tbody','tr','th','td','strong','b','em','a','br'}

def clean(node):
    fragment = BeautifulSoup(str(node), 'html.parser')
    for item in list(fragment.select('script,style,button,input,textarea,svg,img,video,nav,.day-cover,.day-media,.day-notes,.no-print,.visually-hidden,.tag-row,.city-guide-link,.section-label,.section-bridge,.bar-track')):
        item.decompose()
    for item in list(fragment.find_all(True)):
        if item.name not in allowed:
            item.unwrap()
            continue
        href = item.get('href','')
        item.attrs = {}
        if item.name == 'a':
            if href.startswith(('https://','http://')):
                item['href'] = href
                item['target'] = '_blank'
                item['rel'] = 'noopener'
            else:
                item.unwrap()
    return str(fragment).strip()

entries = {}
by_place = {p['id']: [] for p in atlas['places']}
shared = []
unused = []
def add(key, title, node, targets=(), common=False):
    entries[key] = {'title': title, 'html': clean(node)}
    for place in targets:
        by_place[place].append(key)
    if common:
        shared.append(key)
    elif not targets:
        unused.append(key)

for day in source.select('#days details.day'):
    key = day['id']
    targets = [p['id'] for p in atlas['places'] if key in p.get('legacyDays', [])]
    title = day.select_one('.day-date b').get_text(' ',strip=True) + ' · 行前安排'
    add(key, title, day.select_one('.day-body'), targets)

city_map = {'yinchuan':['helan','jiuhe'], 'zhangye':['zhangye'], 'dunhuang':['dunhuang','siju','nightmarket'], 'lenghu':['lenghu'], 'delingha':['delingha'], 'qinghaihu':['lake','camp'], 'xining':['xining']}
for city in source.select('#citywalk details.city-guide'):
    name = city.select_one('summary strong').get_text(' ',strip=True)
    add(city['id'],name + ' · 城市散步',city,city_map.get(city['id'].removeprefix('city-'),[]))

spot_map = {'贺兰山':['helan','jiuhe'], '平山湖大峡谷':['pingshanhu'], '张掖城里':['zhangye'], '七彩丹霞':['danxia'], '鸣沙山月牙泉':['mingsha'], '沙州夜市':['nightmarket'], '敦煌市区漫步':['dunhuang'], '黑独山':['heidu'], '乌素特水上雅丹':['water'], 'G315 上的 U 形弯':['chaerhan'], '德令哈':['delingha'], '青海湖东岸':['lake','camp']}
for i, spot in enumerate(source.select('.spot-slide')):
    name = spot.select_one('h3').get_text(' ',strip=True)
    add('spot-'+str(i),name,spot.select_one('.spot-slide-card'),spot_map.get(name,[]))

add('overview','出发前的约定',source.select_one('#overview'),common=True)
add('route','路段与导航',source.select_one('#route'),common=True)
add('budget','订房与预算',source.select_one('#budget'),common=True)
add('todo','出发清单',source.select_one('#todo'),common=True)
for extra in source.select('#extras .extra-panel'):
    if extra.get('data-panel') == 'weather':
        continue
    add('extra-'+extra['data-panel'],extra.select_one('h3').get_text(' ',strip=True),extra,common=True)

# These are archived plans, not evidence of an actual hotel stay or payment.
stay_map = {'9.25':'helan','9.26':'jiuhe','9.27':'zhangye','9.28':'dunhuang','9.29':'dunhuang','10.1':'water','10.3':'lake'}
for i, stay in enumerate(source.select('.stay-list > details')):
    text = stay.get_text(' ',strip=True)
    target = next((place for day,place in stay_map.items() if text.startswith(day)),None)
    if target:
        add('stay-'+str(i),'原订住宿',stay,[target])

data = {'entries':entries,'byPlace':by_place,'shared':shared,'unused':unused}
(root / 'scripts/journey-archive.js').write_text('window.JOURNEY_ARCHIVE = '+json.dumps(data,ensure_ascii=False,indent=2)+';\n',encoding='utf-8')
print(f'Integrated {len(entries)} archive entries across {sum(bool(v) for v in by_place.values())} places; {len(unused)} saved for another trip.')
