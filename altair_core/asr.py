"""Japanese offline recognition; no always-on microphone or retained recordings."""
import atexit,base64,json,os,re,subprocess,sys,threading,time,uuid
from collections import OrderedDict
from pathlib import Path
ROOT=Path(os.environ.get('ALTAIR_ROOT',Path(__file__).resolve().parents[1])).resolve()
HOME=Path(os.environ.get('ALTAIR_ASR_HOME',ROOT/'.altair-runtime/asr-ja')).resolve()
_lock=threading.Lock();_state=threading.RLock();_active=None;_cancelled=OrderedDict()
def installed():return (HOME/'python/vosk').is_dir() and (HOME/'vosk-model-small-ja-0.22/am/final.mdl').is_file()
def status():return {'installed':installed(),'language':'ja','offline':True,'max_seconds':15,'busy':_lock.locked(),'retains_recordings':False}
def validate_audio(value):
    if not isinstance(value,str) or not 856<=len(value)<=640000:raise ValueError('Âm thanh cần từ 0,02 đến 15 giây, PCM16 mono 16 kHz.')
    try:pcm=base64.b64decode(value,validate=True)
    except (ValueError,TypeError):raise ValueError('Âm thanh không hợp lệ.') from None
    if not 640<=len(pcm)<=480000 or len(pcm)%2:raise ValueError('Âm thanh PCM16 không hợp lệ.')
    return pcm
def cancel(job_id=None):
    if job_id is not None and not re.fullmatch('[a-f0-9]{32}',str(job_id)):raise ValueError('Mã nhận dạng không hợp lệ.')
    with _state:
        if job_id:
            _cancelled[job_id]=time.monotonic()
            while len(_cancelled)>16:_cancelled.popitem(last=False)
        active=_active
        process=active[1] if active and (job_id is None or job_id==active[0]) else None
    if process and process.poll() is None:
        process.terminate()
        try:process.wait(3)
        except subprocess.TimeoutExpired:process.kill()
        if _lock.acquire(timeout=2):_lock.release()
def recognize(value,job_id=None):
    global _active
    pcm=validate_audio(value)
    job_id=job_id or uuid.uuid4().hex
    if not isinstance(job_id,str) or not re.fullmatch("[a-f0-9]{32}",job_id):raise ValueError("Mã nhận dạng không hợp lệ.")
    if not installed():raise RuntimeError('Chưa cài bộ nghe tiếng Nhật offline.')
    from . import runtime as rt
    from .litert_backend import available_bytes
    if not _lock.acquire(False):raise rt.BusyError('Em đang nhận dạng một câu khác.')
    lease=False;process=None;start=time.monotonic()
    try:
        if not rt._inference_lock.acquire(False):raise rt.BusyError('Em đang xử lý. Chủ nhân chờ một chút nhé.')
        lease=True;free=available_bytes()
        if free is not None and free<900*1024**2:
            from . import litert_backend
            if litert_backend.loaded():litert_backend.unload();free=available_bytes()
        if free is not None and free<600*1024**2:raise RuntimeError('RAM trống thấp. Em chưa nạp bộ nghe tiếng Nhật.')
        env=os.environ.copy();env.update(ALTAIR_ASR_HOME=str(HOME),PYTHONIOENCODING='utf-8',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
        with _state:
            if job_id in _cancelled:raise RuntimeError('Đã dừng nhận dạng.')
        process=subprocess.Popen([sys.executable,'-I',str(Path(__file__).with_name('asr_worker.py'))],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        with _state:
            _active=(job_id,process)
            if job_id in _cancelled:process.terminate()
        try:out,error=process.communicate(pcm,timeout=30)
        except subprocess.TimeoutExpired:process.kill();process.communicate();raise RuntimeError('Em đã dừng nhận dạng vì quá thời gian.') from None
        with _state:
            if job_id in _cancelled:raise RuntimeError('Đã dừng nhận dạng.')
        if process.returncode or len(out)>10000:raise RuntimeError('Chưa nhận dạng được. Chủ nhân thử nói lại rõ hơn nhé.')
        result=json.loads(out.decode('utf-8'))
        if not isinstance(result.get('text'),str):raise RuntimeError('Kết quả nhận dạng không hợp lệ.')
        return {'text':result['text'][:500],'language':'ja','elapsed_s':round(time.monotonic()-start,3),'worker_exited':True}
    finally:
        if process and process.poll() is None:process.kill();process.communicate()
        with _state:
            _active=None;_cancelled.pop(job_id,None)
        if lease:rt._inference_lock.release()
        _lock.release()
atexit.register(cancel)
