"""Bounded, local Vietnamese TTS. Heavy libraries live only in a short-lived worker."""
from __future__ import annotations
import atexit,hashlib,io,json,os,re,subprocess,sys,threading,time,uuid,wave
from collections import OrderedDict
from pathlib import Path

ROOT=Path(os.environ.get('ALTAIR_ROOT',Path(__file__).resolve().parents[1])).resolve()
HOME=Path(os.environ.get('ALTAIR_TTS_HOME',ROOT/'.altair-runtime/tts')).resolve()
JP_HOME=Path(os.environ.get('ALTAIR_JP_HOME',ROOT/'.altair-runtime/tts-ja')).resolve()
MAX_CHARS=500
_lock=threading.Lock();_state=threading.RLock();_active=None;_cancelled=OrderedDict();_cache=OrderedDict()
_last={}

class VoiceBusyError(RuntimeError):pass
class VoiceCancelled(RuntimeError):pass

def installed():return (JP_HOME/'voice/model.onnx').is_file() and (JP_HOME/'voice/jf_alpha.bin').is_file() and (JP_HOME/'python/misaki/ja.py').is_file() and (HOME/'python/onnxruntime').is_dir()
def status():return {'installed':installed(),'voice':'Kokoro jf_alpha · nữ Nhật thay thế','language':'ja','subtitles':'vi','character_voice':False,'offline':True,'threads':2,'max_chars':MAX_CHARS,'busy':_lock.locked(),'last':dict(_last)}

def prepare_text(text):
    if not isinstance(text,str) or not 1<=len(text.strip())<=MAX_CHARS:raise ValueError('Nội dung đọc cần từ 1 đến 500 ký tự.')
    text=re.sub(r'https?://\S+','',text)
    text=re.sub(r'\[\d+\]|[*#`]|[\x00-\x08\x0b\x0c\x0e-\x1f]','',text)
    text=' '.join(text.split())
    if not text:raise ValueError('Chưa có nội dung để đọc.')
    return text

def cancel(job_id=None):
    global _active
    waiting=None
    with _state:
        if job_id:
            if not re.fullmatch(r'[a-f0-9]{32}',str(job_id)):raise ValueError('Mã giọng đọc không hợp lệ.')
            _cancelled[job_id]=time.monotonic()
            while len(_cancelled)>16:_cancelled.popitem(last=False)
        if _active and (job_id is None or job_id==_active[0]):
            process=_active[1]
            if process.poll() is None:process.terminate();waiting=process
    if waiting:
        try:waiting.wait(timeout=3)
        except subprocess.TimeoutExpired:waiting.kill()
        if _lock.acquire(timeout=2):_lock.release()

def clear_cache():
    with _state:_cache.clear()

def synthesize(text,job_id=None,speed=.95):
    global _active,_last
    text=prepare_text(text)
    if job_id is None:job_id=uuid.uuid4().hex
    if not isinstance(job_id,str) or not re.fullmatch(r'[a-f0-9]{32}',job_id):raise ValueError('Mã giọng đọc không hợp lệ.')
    if isinstance(speed,bool):raise ValueError('Tốc độ đọc không hợp lệ.')
    try:speed=float(speed)
    except (TypeError,ValueError):raise ValueError('Tốc độ đọc không hợp lệ.') from None
    if not .8<=speed<=1.2:raise ValueError('Tốc độ đọc phải từ 0,8 đến 1,2.')
    if not installed():raise RuntimeError('Chưa cài giọng Nhật offline cho Altair.')
    if not _lock.acquire(False):raise VoiceBusyError('Em đang chuẩn bị một giọng đọc khác.')
    from . import runtime as rt
    started=time.monotonic();process=None;lease=False
    try:
        with _state:
            if job_id in _cancelled:raise VoiceCancelled('Đã dừng giọng đọc.')
            key=hashlib.sha256(json.dumps([text,speed],ensure_ascii=False).encode()).hexdigest()
            cached=_cache.get(key)
            if cached and time.monotonic()-cached[0]<120:
                _cache.move_to_end(key);_last={'cached':True,'elapsed_s':round(time.monotonic()-started,3)};return cached[1]
        if not rt._inference_lock.acquire(False):raise VoiceBusyError('Em đang xử lý câu hỏi. Chủ nhân chờ câu trả lời hoàn tất nhé.')
        lease=True
        from .litert_backend import available_bytes
        free=available_bytes()
        if free is not None and free<900*1024**2:
            from . import litert_backend
            if litert_backend.loaded():litert_backend.unload();free=available_bytes()
        if free is not None and free<600*1024**2:raise RuntimeError('RAM trống đang thấp. Em giữ câu trả lời bằng chữ và chưa nạp giọng đọc.')
        env=os.environ.copy();env['ALTAIR_TTS_HOME']=str(HOME);env['ALTAIR_JP_HOME']=str(JP_HOME);env['ALTAIR_ROOT']=str(ROOT);env['PYTHONIOENCODING']='utf-8';env['OMP_NUM_THREADS']='2'
        with _state:
            if job_id in _cancelled:raise VoiceCancelled('Đã dừng giọng đọc.')
            process=subprocess.Popen([sys.executable,'-I',str(Path(__file__).with_name('tts_japanese_worker.py'))],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
            _active=(job_id,process)
        try:audio,error=process.communicate(json.dumps({'text':text,'speed':speed},ensure_ascii=False).encode(),timeout=45)
        except subprocess.TimeoutExpired:
            process.kill();process.communicate();raise RuntimeError('Giọng đọc xử lý quá lâu; em đã dừng để tiết kiệm máy.') from None
        with _state:
            if job_id in _cancelled:raise VoiceCancelled('Đã dừng giọng đọc.')
        if process.returncode or not 44<len(audio)<=2_100_000:raise RuntimeError('Chưa tạo được giọng đọc offline. Câu trả lời bằng chữ vẫn dùng được.')
        try:
            with wave.open(io.BytesIO(audio)) as wav:
                if wav.getnchannels()!=1 or wav.getsampwidth()!=2 or wav.getframerate()!=24000:raise RuntimeError('Định dạng âm thanh không phù hợp.')
                duration=wav.getnframes()/wav.getframerate()
        except (wave.Error,EOFError):raise RuntimeError('Âm thanh chưa hoàn tất. Em đã giữ lại câu trả lời bằng chữ.') from None
        with _state:
            _cache[key]=(time.monotonic(),audio)
            while len(_cache)>2 or sum(len(v[1]) for v in _cache.values())>4*1024**2:_cache.popitem(last=False)
        _last={'cached':False,'elapsed_s':round(time.monotonic()-started,3),'audio_s':round(duration,3),'worker_exited':True}
        return audio
    finally:
        if process and process.poll() is None:process.kill();process.communicate()
        with _state:
            if _active and _active[0]==job_id:_active=None
            _cancelled.pop(job_id,None)
        if lease:rt._inference_lock.release()
        _lock.release()

atexit.register(cancel)
