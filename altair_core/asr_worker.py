"""Recognize one bounded PCM utterance. Exit immediately to release ASR RAM."""
import json,os,socket,sys
from pathlib import Path
def main():
    home=Path(os.environ['ALTAIR_ASR_HOME'])
    sys.path.insert(0,str(home/'python'))
    def offline(*a,**k):raise RuntimeError('ASR is offline')
    from vosk import Model,KaldiRecognizer,SetLogLevel
    socket.create_connection=offline;socket.socket.connect=offline;socket.socket.connect_ex=offline
    SetLogLevel(-1)
    pcm=sys.stdin.buffer.read(480001)
    if not 640<=len(pcm)<=480000 or len(pcm)%2:raise ValueError('Invalid PCM audio')
    model=Model(str(home/'vosk-model-small-ja-0.22'))
    rec=KaldiRecognizer(model,16000)
    parts=[]
    for i in range(0,len(pcm),8000):
        if rec.AcceptWaveform(pcm[i:i+8000]):parts.append(json.loads(rec.Result()).get('text',''))
    parts.append(json.loads(rec.FinalResult()).get('text',''))
    sys.stdout.buffer.write(json.dumps({'text':''.join(parts).strip()[:500],'language':'ja'},ensure_ascii=False).encode('utf-8'));sys.stdout.buffer.flush()
if __name__=='__main__':main()
