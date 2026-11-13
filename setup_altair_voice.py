"""One-time installation of Altair's free local Vietnamese voice. No runtime downloads."""
import hashlib,json,subprocess,sys,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parent;HOME=ROOT/'.altair-runtime/tts'
def main():
    deps=HOME/'python';voice=HOME/'voice';voice.mkdir(parents=True,exist_ok=True)
    subprocess.run([sys.executable,'-m','pip','install','--disable-pip-version-check','--target',str(deps),'piper-tts==1.8.0','onnxruntime==1.31.1','numpy==2.4.6'],check=True)
    base='https://huggingface.co/rhasspy/piper-voices/resolve/main/vi/vi_VN/vais1000/medium/'
    expected={'vi_VN-vais1000-medium.onnx':'ec7c89e2c85f4d1edc24b6120c18aaf1bda614f06b511567eb9c7c0de15e2dab','vi_VN-vais1000-medium.onnx.json':'fafb9da1354ed4b77c31af228ed41fb41cd825c14cffa105454b25e6ae751ee0','MODEL_CARD':'302db8a930ffc2b1c2181db26deaf8272116eca2b08b8f80da6375b0a994af7b'}
    for name,digest in expected.items():
        path=voice/name
        if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest()==digest:continue
        temp=path.with_name(name+'.download')
        with urllib.request.urlopen(base+name,timeout=90) as response,temp.open('wb') as output:
            while data:=response.read(1024*1024):output.write(data)
        if hashlib.sha256(temp.read_bytes()).hexdigest()!=digest:raise RuntimeError('Voice checksum mismatch; the existing file was not replaced.')
        temp.replace(path)
    print('Giọng nữ Việt offline đã sẵn sàng. Mở lại Altair để dùng.')
if __name__=='__main__':main()
