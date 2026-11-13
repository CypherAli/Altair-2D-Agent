/* Push-to-talk Japanese recognition; streams never leave the loopback server. */
(() => {
 const downsample=(chunks,rate)=>{
  const length=chunks.reduce((n,a)=>n+a.length,0),input=new Float32Array(length);let pos=0;
  for(const a of chunks){input.set(a,pos);pos+=a.length;}
  const out=new Int16Array(Math.floor(length*16000/rate));
  for(let i=0;i<out.length;i++){const a=Math.floor(i*rate/16000),b=Math.max(a+1,Math.floor((i+1)*rate/16000));let sum=0;for(let j=a;j<b&&j<length;j++)sum+=input[j];out[i]=Math.round(Math.max(-1,Math.min(1,sum/(b-a)))*32767);}
  return out;
 };
 if(typeof module==='object'&&module.exports)module.exports={downsample};
 if(typeof window==='undefined')return;
 class Listener {
  constructor(character){this.character=character;this.phase='idle';this.generation=0;this.chunks=[];this.timer=null;this.abort=null;this.count=0;}
  show(text){this.character.bubble.textContent=text;this.character.caption.textContent=text;}
  async start(){
   if(this.phase!=='idle')return;if(this.character.interactionBusy){this.show('Em đang xử lý câu trước. Chủ nhân đợi một chút nhé.');return;}this.character.unlockAudio().catch(()=>{});const token=++this.generation;this.phase='opening';
   await this.character.stopSpeech();
   try{
    const state=await (await fetch('/api/asr/status')).json();if(!state.installed)throw Error('Chưa cài bộ nghe tiếng Nhật offline.');if(token!==this.generation)return;
    if(!navigator.mediaDevices?.getUserMedia)throw Error('Microphone cần mở trong ứng dụng Altair hoặc localhost.');
    const stream=await navigator.mediaDevices.getUserMedia({audio:{channelCount:1,echoCancellation:true,noiseSuppression:true},video:false});
    if(token!==this.generation){stream.getTracks().forEach(t=>t.stop());return;}
    this.stream=stream;const context=new AudioContext();this.context=context;
    await context.audioWorklet.addModule('mic-worklet.js');if(token!==this.generation)return this.release();
    this.source=context.createMediaStreamSource(stream);this.processor=new AudioWorkletNode(context,'altair-pcm');this.gain=context.createGain();this.gain.gain.value=0;
    this.chunks=[];this.count=0;this.processor.port.onmessage=e=>{if(this.phase==='recording'&&this.count<context.sampleRate*15){this.chunks.push(e.data);this.count+=e.data.length;}};
    this.source.connect(this.processor);this.processor.connect(this.gain);this.gain.connect(context.destination);await context.resume();if(token!==this.generation)return this.release();
    this.phase='recording';this.character.root.dataset.listening='true';this.character.set('listening');this.show('Em đang nghe tiếng Nhật… Chạm lại nút mic để gửi.');
    this.timer=setTimeout(()=>this.finish(),14000);
   }catch(error){if(token!==this.generation)return;await this.release();this.phase='idle';this.show(error.name==='NotAllowedError'?'Chủ nhân cần cho Altair dùng microphone trong hộp thoại của máy.':error.message);}
  }
  async release(){clearTimeout(this.timer);this.timer=null;this.processor&&(this.processor.port.onmessage=null);this.source?.disconnect();this.processor?.disconnect();this.gain?.disconnect();this.stream?.getTracks().forEach(t=>t.stop());this.stream=null;this.source=this.processor=this.gain=null;if(this.context){await this.context.close().catch(()=>{});this.context=null;}this.character.root.dataset.listening='false';}
  async finish(){
   if(this.phase!=='recording')return;this.phase='recognizing';const token=this.generation,rate=this.context.sampleRate,pcm=downsample(this.chunks,rate);this.chunks=[];await this.release();if(token!==this.generation)return;
   if(pcm.length<1600){this.phase='idle';this.show('Câu nói quá ngắn. Chủ nhân thử lại nhé.');return;}
   this.character.set('thinking');this.show('Em đang nhận dạng tiếng Nhật trên máy…');
   try{
    this.jobId=crypto.randomUUID().replaceAll('-','');this.abort=new AbortController();const bytes=new Uint8Array(pcm.buffer);let raw='';for(let i=0;i<bytes.length;i+=8192)raw+=String.fromCharCode(...bytes.subarray(i,i+8192));
    const response=await fetch('/api/asr',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({pcm:btoa(raw),id:this.jobId}),signal:this.abort.signal});const result=await response.json();
    if(token!==this.generation)return;if(!response.ok)throw Error(result.error||'Chưa nhận dạng được.');
    this.phase='idle';this.character.set('idle');
    if(!result.text?.trim()){this.show('Em chưa nghe rõ tiếng Nhật. Chủ nhân thử lại nhé.');return;}
    this.character.root.dataset.heard=result.text;window.altairJapaneseInput?.(result.text);
   }catch(error){if(token!==this.generation)return;this.phase='idle';this.character.set('idle');if(error.name!=='AbortError')this.show(error.message);}
   finally{if(token===this.generation){this.abort=null;this.jobId=null;}}
  }
  async cancel(){++this.generation;this.abort?.abort();const id=this.jobId;this.jobId=null;this.chunks=[];await this.release();this.phase='idle';if(id)await fetch('/api/asr/stop',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id})}).catch(()=>{});}

  toggle(){return this.phase==='recording'?this.finish():this.phase==='idle'?this.start():this.cancel();}
 }
 window.AltairListener=Listener;
 window.addEventListener('pagehide',()=>window.altairListener?.cancel());
 document.addEventListener('visibilitychange',()=>{if(document.hidden)window.altairListener?.cancel();});
})();
