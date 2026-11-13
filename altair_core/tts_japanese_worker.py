"""One Japanese CPU speech job; no network, GPU or persistent model process."""
import io,json,os,socket,sys,wave,time
from pathlib import Path

def main():
    started=time.monotonic()
    def trace(label):
        if os.environ.get("ALTAIR_VOICE_PROFILE"):print(label,round(time.monotonic()-started,3),file=sys.stderr,flush=True)
    home=Path(os.environ['ALTAIR_JP_HOME'])
    sys.path.insert(0,str(home/'python'))
    # Reuse the installed, pinned ONNX runtime from the existing offline voice.
    sys.path.append(str(Path(os.environ['ALTAIR_ROOT'])/'.altair-runtime/tts/python'))
    def offline(*a,**k):raise RuntimeError('Speech synthesis is offline.')
    socket.create_connection=offline;socket.socket=offline
    import numpy as np
    import onnxruntime as ort
    from misaki.ja import JAG2P
    ort.disable_telemetry_events()
    job=json.loads(sys.stdin.buffer.read(12000).decode('utf-8'))
    text=job['text'];speed=float(job.get('speed',.95))
    if not isinstance(text,str) or not 1<=len(text)<=500 or not .8<=speed<=1.2:raise ValueError('Invalid Japanese speech request')
    trace("imports")
    phonemes,_=JAG2P(version='pyopenjtalk')(text)
    trace("g2p")
    vocab=json.loads((home/'voice/config.json').read_text(encoding='utf-8'))['vocab']
    options=ort.SessionOptions();options.intra_op_num_threads=2;options.inter_op_num_threads=1
    options.enable_cpu_mem_arena=False;options.enable_mem_pattern=False
    session=ort.InferenceSession(str(home/'voice/model.onnx'),sess_options=options,providers=['CPUExecutionProvider'])
    trace("session")
    voice=np.fromfile(home/'voice/jf_alpha.bin',dtype=np.float32).reshape(-1,1,256)
    pieces=[]
    # A single bounded utterance. Reject oversized phonemes instead of truncating speech silently.
    ids=[vocab[c] for c in phonemes if c in vocab]
    if not ids or len(ids)>500:raise ValueError('Japanese speech is too long')
    audio=session.run(None,{'input_ids':np.array([[0,*ids,0]],dtype=np.int64),
        'style':voice[min(len(ids),len(voice)-1)],'speed':np.array([speed],dtype=np.float32)})[0].reshape(-1)
    trace("inference")
    if len(audio)>24000*40:raise ValueError('Speech exceeded 40 seconds')
    data=(np.clip(audio,-1,1)*32767).astype('<i2').tobytes()
    buffer=io.BytesIO()
    with wave.open(buffer,'wb') as wav:
        wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(24000);wav.writeframes(data)
    sys.stdout.buffer.write(buffer.getvalue());sys.stdout.buffer.flush()

if __name__=='__main__':main()
