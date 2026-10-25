"""Local V3 place edits: full-quality stills, matched Live Photos, paper framing, music.

The manifest stays local. Only derived films/posters and a path-free public index are published.
Source photos, original MOV files, and their metadata are never modified or copied to the website.
"""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
import argparse
import json
import math
import subprocess

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter
import imageio_ffmpeg
import pillow_heif

pillow_heif.register_heif_opener()
ROOT=Path(__file__).resolve().parents[1]
FFMPEG=imageio_ffmpeg.get_ffmpeg_exe()
OUT=ROOT/'media/films/v3'
STILLS=ROOT/'media/stills/v3'
TEMP=ROOT/'_tmp_dl/v3-render'
FPS=24
PAPER='#f1e8d5'
FONT=Path('C:/Windows/Fonts')

def font(size,serif=False):
    return ImageFont.truetype(str(FONT/('simsun.ttc' if serif else 'msyh.ttc')),max(10,int(size)))

@lru_cache(maxsize=12)
def photo(path):
    with Image.open(path) as im:
        result=ImageOps.exif_transpose(im).convert('RGB')
        result.thumbnail((2400,2400),Image.Resampling.LANCZOS)
        return result

@lru_cache(maxsize=2)
def paper(size):
    w,h=size
    rng=np.random.default_rng(20261025)
    base=np.array([242,234,215]).reshape(1,1,3)
    noise=rng.normal(0,.65,(h,w,1))
    gradient=np.linspace(2,-4,h).reshape(h,1,1)
    im=Image.fromarray(np.uint8(np.clip(base+noise+gradient,0,255)))
    draw=ImageDraw.Draw(im)
    # Small folded-paper corner, outside the photographs.
    draw.polygon([(w*.94,0),(w,0),(w,h*.065)],fill='#e6d6b8')
    draw.line([(w*.94,0),(w,h*.065)],fill='#c8af87',width=1)
    return im

def put_card(im,image,box):
    cx,cy,maxw,maxh=box
    contained=ImageOps.contain(image,(int(maxw),int(maxh)),Image.Resampling.LANCZOS)
    border=max(8,round(im.width*.008))
    x=round(cx-contained.width/2);y=round(cy-contained.height/2)
    shadow=Image.new('RGBA',im.size)
    ImageDraw.Draw(shadow).rounded_rectangle((x-border+5,y-border+7,x+contained.width+border+5,y+contained.height+border+7),radius=2,fill=(93,72,43,52))
    im=Image.alpha_composite(im.convert('RGBA'),shadow.filter(ImageFilter.GaussianBlur(6)))
    d=ImageDraw.Draw(im)
    d.rectangle((x-border,y-border,x+contained.width+border,y+contained.height+border),fill='#fffaf0')
    im.paste(contained,(x,y))
    # Narrow paper tape stays off faces and important scenery.
    tape=Image.new('RGBA',(int(im.width*.095),max(10,int(im.width*.014))),(195,165,109,96)).rotate(-5,expand=True)
    im.paste(tape,(x+round(contained.width*.16),y-border-round(tape.height*.35)),tape)
    return im.convert('RGB'),(x,y,contained.width,contained.height)

def compose(film,shot,index,size):
    w,h=size;tall=h>w
    im=paper(size).copy()
    source=photo(shot['source'])
    is_vertical=source.height>source.width*1.1
    other=film['shots'][index+1 if index+1<len(film['shots']) else max(0,index-1)]
    # Keep night sky paired with night sky, rather than a daytime companion.
    if '星空' in shot['title'] or '夜空' in shot['title']:
        other=shot
    if not tall and is_vertical and len(film['shots'])>1:
        im,main=put_card(im,source,(w*.275,h*.545,w*.43,h*.75))
        im,_=put_card(im,photo(other['source']),(w*.735,h*.545,w*.42,h*.73))
    elif tall and not is_vertical and len(film['shots'])>1:
        im,main=put_card(im,source,(w*.50,h*.365,w*.90,h*.45))
        im,_=put_card(im,photo(other['source']),(w*.51,h*.765,w*.84,h*.30))
    else:
        im,main=put_card(im,source,(w*.50,h*.54,w*.91,h*.77))
    d=ImageDraw.Draw(im)
    title_size=w*(.044 if tall else .026)
    title_font=font(title_size,True)
    while d.textbbox((0,0),film['title'],font=title_font)[2]>w*.89:
        title_size-=1;title_font=font(title_size,True)
    d.text((w*.045,h*.037),film['title'],font=title_font,fill='#665139')
    d.text((w*.047,h*.093 if tall else h*.097),film['date'],font=font(w*(.024 if tall else .014)),fill='#9d8059')
    d.line((w*.047,h*.955,w*.16,h*.955),fill='#bda47c',width=1)
    return im,main

def read_motion(motion,window,seconds):
    _,_,w,h=window
    start=max(0,float(motion.get('recommendedStart',.2)))
    duration=min(float(motion.get('recommendedDuration',2)),max(.4,seconds-.75),2.45)
    if start+duration>motion['duration']:
        duration=max(.3,motion['duration']-start-.06)
    vf=f'fps={FPS},scale={w}:{h}:force_original_aspect_ratio=decrease:flags=lanczos,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=0xfffaf0,setsar=1'
    command=[FFMPEG,'-v','error','-ss',str(start),'-i',motion['path'],'-t',str(duration),'-an','-vf',vf,'-threads','1','-pix_fmt','rgb24','-f','rawvideo','pipe:1']
    process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    frames=[];chunk_size=w*h*3
    while True:
        raw=process.stdout.read(chunk_size)
        if not raw:break
        if len(raw)!=chunk_size:raise RuntimeError('Incomplete decoded Live frame')
        frames.append(Image.frombytes('RGB',(w,h),raw))
    error=process.stderr.read().decode(errors='replace');code=process.wait()
    if code or not frames:raise RuntimeError(f"Live {motion['id']} decode failed: {error[-600:]}")
    return frames

def zoom(im,t,index):
    amount=.006*min(1,max(0,t))
    if index%2:amount=.006-amount
    w,h=im.size
    return im.transform(im.size,Image.Transform.EXTENT,(w*amount,h*amount,w*(1-amount),h*(1-amount)),Image.Resampling.BILINEAR)

def render(film,orientation,force=False):
    size=(1280,720) if orientation=='wide' else (720,1280)
    output=OUT/f"{film['id']}-{orientation}.mp4"
    poster=STILLS/f"{film['id']}-{orientation}.jpg"
    if output.exists() and poster.exists() and not force:
        return {'id':film['id'],'orientation':orientation,'bytes':output.stat().st_size,'duration':film['duration'],'cached':True}
    cross=.34 if len(film['shots'])>1 else 0
    seconds=(film['duration']+cross*(len(film['shots'])-1))/len(film['shots'])
    scenes=[]
    for index,shot in enumerate(film['shots']):
        still,window=compose(film,shot,index,size)
        motion=read_motion(shot['motion'],window,seconds) if shot.get('motion') else []
        scenes.append((still,window,motion))
        if shot['id']==film['posterId']:still.save(poster,quality=91)
    if not poster.exists():scenes[0][0].save(poster,quality=91)
    def scene_frame(index,local):
        still,window,moving=scenes[index]
        if not moving:return zoom(still,local/seconds,index)
        start=.28;fade=.18;motion_duration=len(moving)/FPS
        if local<start:return still
        tick=local-start
        if tick>motion_duration+fade:return still
        tile=moving[min(len(moving)-1,max(0,int(tick*FPS)))]
        frame=still.copy();frame.paste(tile,window[:2])
        alpha=min(1,tick/fade,max(0,(motion_duration+fade-tick)/fade))
        return Image.blend(still,frame,alpha) if alpha<1 else frame
    starts=[index*(seconds-cross) for index in range(len(scenes))]
    silent=TEMP/f"{film['id']}-{orientation}-silent.mp4"
    log=TEMP/f"{film['id']}-{orientation}.log"
    cmd=[FFMPEG,'-y','-hide_banner','-loglevel','error','-f','rawvideo','-pix_fmt','rgb24','-video_size',f'{size[0]}x{size[1]}','-framerate',str(FPS),'-i','-','-an','-c:v','libx264','-preset','veryfast','-crf','20','-pix_fmt','yuv420p','-profile:v','high','-level','4.0','-movflags','+faststart','-threads','2',str(silent)]
    with log.open('wb') as err:
        process=subprocess.Popen(cmd,stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=err)
        try:
            for n in range(round(film['duration']*FPS)):
                t=n/FPS;index=max(i for i,start in enumerate(starts) if start<=t)
                local=t-starts[index];frame=scene_frame(index,local)
                if index and local<cross:
                    previous=scene_frame(index-1,t-starts[index-1]);alpha=local/cross
                    frame=Image.blend(previous,frame,alpha*alpha*(3-2*alpha))
                process.stdin.write(frame.tobytes())
        finally:process.stdin.close()
        if process.wait():raise RuntimeError(log.read_text(errors='replace'))
    track=ROOT/'media/music'/f"{film['music']}.wav"
    audio=f"loudnorm=I=-22:TP=-2:LRA=8,afade=t=in:st=0:d=0.4,afade=t=out:st={film['duration']-1.2:.3f}:d=1.2"
    subprocess.run([FFMPEG,'-y','-v','error','-i',str(silent),'-stream_loop','-1','-i',str(track),'-map','0:v:0','-map','1:a:0','-map_metadata','-1','-map_chapters','-1','-c:v','copy','-c:a','aac','-b:a','128k','-ar','48000','-af',audio,'-t',str(film['duration']),'-movflags','+faststart',str(output)],check=True)
    return {'id':film['id'],'orientation':orientation,'bytes':output.stat().st_size,'duration':film['duration'],'width':size[0],'height':size[1],'photos':len(film['shots']),'live':sum(bool(s.get('motion')) for s in film['shots'])}

def public_index(manifest):
    films=[]
    for film in manifest['films']:
        row={k:film[k] for k in ['id','placeId','placeIds','title','date','label','duration']}
        row['stats']={'photos':len(film['shots']),'live':sum(bool(s.get('motion')) for s in film['shots'])}
        for orientation in ['wide','portrait']:
            row[orientation]={'src':f"../../media/films/v3/{film['id']}-{orientation}.mp4",'poster':f"../../media/stills/v3/{film['id']}-{orientation}.jpg"}
        films.append(row)
    return {'version':3,'title':manifest['title'],'films':films}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--ids');parser.add_argument('--orientation',choices=['wide','portrait']);parser.add_argument('--force',action='store_true');parser.add_argument('--manifest',default='notes/place-film-edit-v3.json')
    args=parser.parse_args()
    for folder in [OUT,STILLS,TEMP,ROOT/'preview/v3']:folder.mkdir(parents=True,exist_ok=True)
    manifest=json.loads((ROOT/args.manifest).read_text(encoding='utf-8'))
    wanted=set(args.ids.split(',')) if args.ids else None
    selected=[f for f in manifest['films'] if not wanted or f['id'] in wanted]
    for film in selected:
        if film['id']=='water':
            assert all(s.get('fileTime','').startswith('2026:10:02') and int(s['fileTime'][11:13])<12 for s in film['shots'])
        assert not {'N3599','N3613'} & {s['id'] for s in film['shots']}
    results=[]
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(render,f,o,args.force) for f in selected for o in ([args.orientation] if args.orientation else ['wide','portrait'])]
        for task in as_completed(futures):
            result=task.result();results.append(result);print(json.dumps(result,ensure_ascii=False),flush=True)
    report=ROOT/'notes/place-film-render-v3.json'
    prior=json.loads(report.read_text(encoding='utf-8')) if report.exists() else []
    records={(r['id'],r['orientation']):r for r in prior}
    for result in results:records[(result['id'],result['orientation'])]=result
    report.write_text(json.dumps(list(records.values()),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (ROOT/'preview/v3/films.json').write_text(json.dumps(public_index(manifest),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

if __name__=='__main__':main()
