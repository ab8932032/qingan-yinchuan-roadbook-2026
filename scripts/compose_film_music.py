"""Three original, quiet instrumental cues, synthesized locally from written note sequences."""
from pathlib import Path
import json
import wave
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'media/music'
RATE=44100


def frequency(midi):return 440*2**((midi-69)/12)


def note(midi,seconds,instrument):
    t=np.arange(int(seconds*RATE))/RATE
    f=frequency(midi)
    if instrument=='pad':
        tone=(np.sin(2*np.pi*f*t)+.22*np.sin(2*np.pi*f*2.003*t)+.08*np.sin(2*np.pi*f*3*t))
        envelope=np.minimum(1,t/.6)*np.minimum(1,(seconds-t)/.9)*np.exp(-t/(seconds*1.2))
    elif instrument=='pluck':
        tone=sum((1/k**1.7)*np.sin(2*np.pi*f*k*t)*np.exp(-t*k/1.8) for k in range(1,7))
        envelope=np.minimum(1,t/.014)*np.exp(-t/1.25)*np.minimum(1,(seconds-t)/.12)
    else:
        tone=sum((1/k**1.9)*np.sin(2*np.pi*f*(k+.0004*k*k)*t)*np.exp(-t*k/3.0) for k in range(1,8))
        envelope=np.minimum(1,t/.012)*np.exp(-t/1.8)*np.minimum(1,(seconds-t)/.14)
    return tone*envelope


def compose(name,bpm,chords,melody,soft=False):
    beat=60/bpm
    seconds=32*beat+2.5
    track=np.zeros((int(seconds*RATE),2),np.float64)
    def add(midi,at,dur,level,instrument,pan=0):
        wavelet=note(midi,dur,instrument)*level
        start=int(at*RATE)
        count=min(len(wavelet),len(track)-start)
        track[start:start+count,0]+=wavelet[:count]*np.sqrt((1-pan)/2)
        track[start:start+count,1]+=wavelet[:count]*np.sqrt((1+pan)/2)
    for bar,chord in enumerate(chords):
        at=bar*4*beat
        add(chord[0]-12,at,3.6*beat,.20,'pad',-.12)
        for pitch in chord:add(pitch,at,4.2*beat,.055 if soft else .04,'pad')
        for i in range(8):
            pitch=chord[[0,1,2,1,3,2,1,2][i]]
            add(pitch,at+i*.5*beat,2.1*beat,.065 if soft else .095,'pluck',(-.3 if i%2 else .3))
    for i,pitch in enumerate(melody):
        if pitch is not None:add(pitch,i*beat,2.6*beat,.105 if soft else .14,'piano',.1)
    # A restrained room tail; no downloaded recordings, samples or scene audio.
    dry=track.copy()
    for delay,gain in [(.19,.11),(.37,.08),(.61,.045)]:
        shift=int(delay*RATE);track[shift:]+=dry[:-shift,::-1]*gain
    peak=np.max(np.abs(track));track*=.22/max(peak,.001)
    ramp=np.minimum(1,np.arange(len(track))/RATE/.5)
    ramp*=np.minimum(1,(len(track)-np.arange(len(track)))/RATE/1.8)
    track*=ramp[:,None]
    pcm=np.int16(np.clip(track,-1,1)*32767)
    file=OUT/(name+'.wav')
    with wave.open(str(file),'wb') as dst:
        dst.setnchannels(2);dst.setsampwidth(2);dst.setframerate(RATE);dst.writeframes(pcm.tobytes())
    return {'file':file.name,'seconds':round(seconds,2),'peakDbFS':round(20*np.log10(np.max(np.abs(track))),1),'rmsDbFS':round(20*np.log10(np.sqrt(np.mean(track**2))),1),'composition':'Original note sequence and local additive synthesis; no external samples.'}


if __name__=='__main__':
    OUT.mkdir(parents=True,exist_ok=True)
    tracks=[
      compose('courtyard',80,[[55,62,67,71],[50,57,62,66],[52,59,64,67],[48,55,60,64]]*2,[71,74,76,74,71,67,69,None,67,71,74,None,76,74,71,None,72,76,79,76,74,71,69,None,67,69,71,74,72,69,67,None]),
      compose('open-road',76,[[50,57,62,65],[46,53,58,62],[53,60,65,69],[48,55,60,64]]*2,[69,None,72,74,77,None,76,74,72,None,69,65,67,None,69,None,74,None,77,79,77,None,74,72,69,None,67,65,64,None,62,None],True),
      compose('lake-light',72,[[48,55,60,64],[45,52,57,60],[53,60,65,69],[55,62,67,71]]*2,[76,None,79,83,81,None,79,None,76,None,74,72,76,None,79,None,77,None,81,84,83,None,79,None,76,None,74,72,71,None,72,None],True)
    ]
    (OUT/'credits.json').write_text(json.dumps({'author':'Original instrumental arrangements created for this travel journal','tracks':tracks},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(tracks,ensure_ascii=False))
