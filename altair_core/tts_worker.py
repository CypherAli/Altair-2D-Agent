"""Isolated CPU speech worker. One bounded job, no downloads, exits to release RAM."""
import io,json,os,socket,sys,wave
from pathlib import Path

def main():
    home=Path(os.environ['ALTAIR_TTS_HOME']).resolve()
    sys.path.insert(0,str(home/'python'))
    # A synthesis job must work without any network access.
    def offline(*args,**kwargs):raise RuntimeError('TTS is offline; network access disabled.')
    socket.create_connection=offline;socket.socket=offline
    import onnxruntime as ort
    from piper import PiperVoice,SynthesisConfig
    from piper.config import PiperConfig
    ort.disable_telemetry_events()
    job=json.loads(sys.stdin.buffer.read(12000).decode('utf-8'))
    text=job['text'];speed=float(job.get('speed',1))
    if not isinstance(text,str) or not 1<=len(text)<=500 or not .8<=speed<=1.2:raise ValueError('Invalid speech request')
    model=home/'voice/vi_VN-vais1000-medium.onnx'
    config=json.loads(model.with_suffix('.onnx.json').read_text(encoding='utf-8'))
    options=ort.SessionOptions();options.intra_op_num_threads=2;options.inter_op_num_threads=1
    options.enable_cpu_mem_arena=False;options.enable_mem_pattern=False
    session=ort.InferenceSession(str(model),sess_options=options,providers=['CPUExecutionProvider'])
    voice=PiperVoice(config=PiperConfig.from_dict(config),session=session)
    buffer=io.BytesIO()
    with wave.open(buffer,'wb') as output:
        output.setnchannels(1);output.setsampwidth(2);output.setframerate(config['audio']['sample_rate'])
        total=0
        for chunk in voice.synthesize(text,SynthesisConfig(length_scale=1/speed,noise_scale=.55,noise_w_scale=.65)):
            total+=len(chunk.audio_int16_bytes)
            if total>22050*2*45:raise ValueError('Speech exceeded 45 seconds')
            output.writeframes(chunk.audio_int16_bytes)
    sys.stdout.buffer.write(buffer.getvalue());sys.stdout.buffer.flush()

if __name__=='__main__':main()
