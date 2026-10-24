"""Render local travel-photo edits and original paper animations. Never edits source media."""
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

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'media' / 'films' / 'v2'
STILLS = ROOT / 'media' / 'stills' / 'v2'
FPS = 24
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
FONT = Path('C:/Windows/Fonts')
MANIFEST = json.loads((ROOT / 'notes/daily-film-edit.json').read_text(encoding='utf-8'))


def font(size, serif=False):
    return ImageFont.truetype(str(FONT / ('simsun.ttc' if serif else 'msyh.ttc')), max(9, int(size)))


def text(draw, xy, value, size, fill='#6c5b45', serif=False, anchor=None):
    draw.text(xy, value, font=font(size, serif), fill=fill, anchor=anchor)


@lru_cache(maxsize=4)
def _paper_base(w, h, night=False):
    rng = np.random.default_rng(20261024)
    base = np.array([239, 229, 208] if not night else [61, 83, 91])
    noise = rng.normal(0, .85, (h, w, 1))
    gradient = np.linspace(3, -5, h).reshape(h, 1, 1)
    return Image.fromarray(np.uint8(np.clip(base + noise + gradient, 0, 255)))


def paper(w,h,night=False):
    return _paper_base(w,h,night).copy()


def landscape(im, kind, phase=0, opacity=1):
    """An original code-native cut-paper landscape, with no invented documentary images."""
    w, h = im.size
    layer = Image.new('RGBA', (w, h))
    d = ImageDraw.Draw(layer)
    poly = lambda pts, c: d.polygon([(int(x*w), int(y*h)) for x, y in pts], fill=c)
    if kind in ['night', 'home']:
        for i in range(44):
            x = ((i * .618034 + .03) % 1) * w
            y = ((i * .377 + .09) % .53) * h
            a = int(130 + 80 * math.sin(phase * 1.3 + i))
            r = 1 if i % 3 else 2
            d.ellipse((x-r,y-r,x+r,y+r), fill=(245,239,214,a))
    if kind in ['lake', 'night']:
        poly([(0,.67),(.22,.64),(.45,.68),(.71,.63),(1,.66),(1,1),(0,1)], '#8eafa8')
        poly([(0,.75),(.26,.73),(.61,.78),(1,.72),(1,1),(0,1)], '#668e91')
        for j in range(5):
            y = h * (.79 + j*.035)
            x = w * (.1 + j*.13) + math.sin(phase+j)*w*.015
            d.line((x,y,x+w*.17,y-h*.004), fill='#bad0c2', width=max(1,w//700))
    else:
        poly([(0,.74),(.19,.67),(.43,.73),(.69,.65),(1,.72),(1,1),(0,1)], '#d7bd91')
        poly([(0,.84),(.3,.76),(.56,.85),(.84,.74),(1,.8),(1,1),(0,1)], '#c5a57c')
    # A series of folded mountains in the distance.
    for i in range(6):
        x = i*.19-.06
        peak = .5 - (i%3)*.035
        poly([(x,.70),(x+.12,peak),(x+.28,.70)], '#a4ad96' if kind!='clay' else '#bb967b')
        poly([(x+.12,peak),(x+.145,.67),(x+.28,.70)], '#84917d' if kind!='clay' else '#9e775f')
    if kind in ['road', 'home', 'desert']:
        poly([(.48,.68),(.53,.68),(.85,1),(.1,1)], '#a3947b')
        for i in range(6):
            yy = .70 + ((i/6 + phase*.10) % 1)*.33
            xx = .505 + (yy-.68)*.025
            d.line((xx*w,yy*h,(xx+.006)*w,(yy+.022)*h), fill='#f4e6c9', width=max(1,int((yy-.65)*w*.013)))
        # A small folded-paper car, moving along the road.
        cx, cy = w*.505, h*(.79+math.sin(phase*.8)*.008)
        cw = w*.075
        d.rounded_rectangle((cx-cw/2,cy-cw*.18,cx+cw/2,cy+cw*.28), radius=cw*.09, fill='#6f807c')
        d.polygon([(cx-cw*.32,cy-cw*.18),(cx-cw*.18,cy-cw*.48),(cx+cw*.22,cy-cw*.48),(cx+cw*.42,cy-cw*.18)], fill='#e7e0c4')
        for xx in [cx-cw*.26,cx+cw*.28]:
            d.ellipse((xx-cw*.09,cy+cw*.16,xx+cw*.09,cy+cw*.34), fill='#736b5c')
    if opacity != 1:
        layer.putalpha(layer.getchannel('A').point(lambda a: int(a*opacity)))
    im.paste(layer, (0,0), layer)


def source_photo(shot):
    # iPhone HEIC previews already decoded by the linked curation; prefer full JPEG when available.
    path = Path(shot['source'])
    try:
        with Image.open(path) as img:
            return ImageOps.exif_transpose(img).convert('RGB')
    except Exception:
        with Image.open(shot['preview']) as img:
            return ImageOps.exif_transpose(img).convert('RGB')


def photo_card(photo, maxw, maxh, angle):
    image = ImageOps.contain(photo, (int(maxw),int(maxh)), Image.Resampling.LANCZOS)
    border = max(8, int(maxw*.025))
    card = Image.new('RGBA', (image.width+2*border,image.height+2*border), '#fbf4e4')
    card.paste(image,(border,border))
    return card.rotate(angle, Image.Resampling.BICUBIC, expand=True)


def compose(day, shot, index, size):
    w, h = size
    tall = h>w
    im = paper(w,h)
    landscape(im,day['kind'],index,opacity=.27)
    d = ImageDraw.Draw(im)
    margin = int(w*.075)
    text(d,(margin,h*.055),f"2026  /  {day['date']}",w*(.029 if tall else .019),fill='#aa8057')
    text(d,(margin,h*.10),day['title'],w*(.058 if tall else .036),serif=True)
    photo = source_photo(shot)
    portrait_photo = photo.height > photo.width*1.1
    if tall:
        card = photo_card(photo,w*.80,h*.61,-1.1 if index%2 else 1.0)
        x,y=(w-card.width)//2,int(h*.22+(h*.61-card.height)/2)
    elif portrait_photo:
        card=photo_card(photo,w*.46,h*.71,-1.2 if index%2 else 1.1)
        x=int(w*.28-card.width/2)
        y=int(h*.20)
    else:
        card=photo_card(photo,w*.87,h*.66,-.7 if index%2 else .6)
        x,y=(w-card.width)//2,int(h*.20)
    shadow=Image.new('RGBA',im.size)
    sd=ImageDraw.Draw(shadow)
    sd.rectangle((x+7,y+9,x+card.width+7,y+card.height+9),fill=(91,72,47,55))
    shadow=shadow.filter(ImageFilter.GaussianBlur(max(3,w//150)))
    im=Image.alpha_composite(im.convert('RGBA'),shadow)
    im.paste(card,(x,y),card)
    if not tall and portrait_photo:
        other=day['shots'][(index+1)%len(day['shots'])]
        companion=photo_card(source_photo(other),w*.40,h*.68,1.0 if index%2 else -1.2)
        xx=int(w*.73-companion.width/2)
        yy=int(h*.22+(h*.68-companion.height)/2)
        shade=Image.new('RGBA',im.size)
        ImageDraw.Draw(shade).rectangle((xx+6,yy+8,xx+companion.width+6,yy+companion.height+8),fill=(91,72,47,42))
        im=Image.alpha_composite(im,shade.filter(ImageFilter.GaussianBlur(max(3,w//160))))
        im.paste(companion,(xx,yy),companion)
    d=ImageDraw.Draw(im)
    # Small translucent paper tape, outside the photograph's subject.
    tx=x+card.width*.18
    ty=y-5
    tape=Image.new('RGBA',(max(28,int(w*.11)),max(10,int(w*.024))),(195,168,115,110)).rotate(-7,expand=True)
    im.paste(tape,(int(tx),int(ty)),tape)
    text(d,(w*.075,h*.94 if not tall else h*.91),shot['label'],w*(.036 if tall else .019),serif=True)
    return im.convert('RGB')


def animated_paper(day,size,t,opening=False):
    w,h=size
    night=day['kind']=='home' or day['kind']=='night'
    im=paper(w,h,night)
    if day['kind']=='home':
        dawn=min(1,max(0,t/13))
        im=Image.blend(im,paper(w,h),dawn*dawn)
        sun=ImageDraw.Draw(im)
        cx,cy=w*.68,h*(.70-.17*dawn)
        radius=w*.035
        sun.ellipse((cx-radius,cy-radius,cx+radius,cy+radius),fill='#e6cb91')
        landscape(im,'home' if dawn<.65 else 'road',t)
        night=dawn<.65
    else:landscape(im,day['kind'],t)
    d=ImageDraw.Draw(im)
    color='#f5ecd5' if night else '#705b40'
    small='#d1c3a5' if night else '#a4845e'
    tall=h>w
    text(d,(w*.5,h*.21),f"2026  /  {day['date']}",w*(.038 if tall else .022),small,anchor='mm')
    text(d,(w*.5,h*.34),day['title'],w*(.065 if tall else .047),color,True,'mm')
    if not day['shots']:
        route={'9.24':'成都  →  银川','9.27':'银川  →  武威  →  张掖','10.5':'西宁  →  成都'}[day['date']]
        text(d,(w*.5,h*.44),route,w*(.032 if tall else .023),small,anchor='mm')
    return im


def zoom(im,progress,index):
    w,h=im.size
    inset=(.006+.014*progress) if index%2==0 else (.02-.014*progress)
    dx=w*inset
    dy=h*inset
    return im.transform((w,h),Image.Transform.EXTENT,(dx,dy,w-dx,h-dy),Image.Resampling.BILINEAR)


def render(day,orientation,force=False):
    size=(1280,720) if orientation=='wide' else (720,1280)
    key=day['date'].replace('.','-')
    output=OUT/f'{key}-{orientation}.mp4'
    poster=STILLS/f'{key}-{orientation}.jpg'
    if output.exists() and poster.exists() and not force:
        return {'day':day['date'],'orientation':orientation,'file':output.name,'bytes':output.stat().st_size,'cached':True}
    w,h=size
    frames=[compose(day,s,i,size) for i,s in enumerate(day['shots'])]
    cross=.42
    if frames:
        segments=[('paper',1.6)]+[(i,3.2) for i in range(len(frames))]+[('paper',1.3)]
        duration=sum(s[1] for s in segments)-cross*(len(segments)-1)
    else:
        segments=[('paper',16)]
        duration=16
    starts=[]
    elapsed=0
    for kind,seconds in segments:
        starts.append(elapsed)
        elapsed+=seconds-cross
    def segment_frame(index,t):
        kind,seconds=segments[index]
        return animated_paper(day,size,t) if kind=='paper' else zoom(frames[kind],min(1,max(0,t/seconds)),kind)
    log=ROOT/'_tmp_dl'/f'film-{key}-{orientation}.log'
    silent=ROOT/'_tmp_dl'/f'film-{key}-{orientation}-v2-silent.mp4'
    cmd=[FFMPEG,'-y','-hide_banner','-loglevel','warning','-f','rawvideo','-pixel_format','rgb24','-video_size',f'{w}x{h}','-framerate',str(FPS),'-i','-','-an','-c:v','libx264','-preset','veryfast','-crf','21','-pix_fmt','yuv420p','-movflags','+faststart','-threads','2',str(silent)]
    with log.open('wb') as err:
        process=subprocess.Popen(cmd,stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=err)
        try:
            count=round(duration*FPS)
            for n in range(count):
                t=n/FPS
                index=max(i for i,start in enumerate(starts) if start<=t)
                local=t-starts[index]
                im=segment_frame(index,local)
                if index>0 and local<cross:
                    prev=segment_frame(index-1,t-starts[index-1])
                    alpha=local/cross
                    alpha=alpha*alpha*(3-2*alpha)
                    im=Image.blend(prev,im,alpha)
                # Posters show a real frame, not a blank intro slate.
                if n==round((2.1 if frames else 3.0)*FPS):im.save(poster,quality=91)
                process.stdin.write(im.tobytes())
        finally:
            process.stdin.close()
        code=process.wait()
    if code:raise RuntimeError(f'{output.name}: {log.read_text(errors="replace")[-1000:]}')
    music=ROOT/'media/music'/(day['music']+'.wav')
    fade=f'volume=1.45,afade=t=in:st=0:d=0.6,afade=t=out:st={max(0,duration-1.5):.3f}:d=1.5'
    subprocess.run([FFMPEG,'-y','-hide_banner','-loglevel','error','-i',str(silent),'-i',str(music),'-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-b:a','128k','-af',fade,'-t',str(count/FPS),'-movflags','+faststart',str(output)],check=True)
    return {'day':day['date'],'orientation':orientation,'file':output.name,'bytes':output.stat().st_size,'seconds':round(duration,2),'width':w,'height':h}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--day')
    parser.add_argument('--force',action='store_true',help='Rebuild the selected derived films, leaving source files untouched.')
    args=parser.parse_args()
    OUT.mkdir(exist_ok=True,parents=True)
    STILLS.mkdir(exist_ok=True,parents=True)
    days=[d for d in MANIFEST['days'] if not args.day or d['date']==args.day]
    results=[]
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(render,day,orientation,args.force) for day in days for orientation in ['wide','portrait']]
        for task in as_completed(futures):
            result=task.result();results.append(result)
            print(json.dumps(result,ensure_ascii=False),flush=True)
    report=ROOT/'notes/daily-film-render-v2.json'
    previous=json.loads(report.read_text(encoding='utf-8')) if report.exists() else []
    merged={row['file']:row for row in previous}
    for row in results:merged[row['file']]={**merged.get(row['file'],{}),**row}
    report.write_text(json.dumps(list(merged.values()),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':main()
