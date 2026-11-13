/* Local artwork, eased poses, draggable camera, audio-clock-driven mouth. */
(() => {
 'use strict';
 const clamp=(v,lo,hi)=>Math.min(hi,Math.max(lo,v));
 function cameraClamp(pan,height,viewHeight,zoom){return clamp(pan,Math.min(0,viewHeight-height*zoom),0);}
 function mouthLevel(samples,previous=0){let energy=0;for(const v of samples)energy+=v*v;const rms=Math.sqrt(energy/Math.max(1,samples.length));const target=rms<.012?0:clamp(rms*8,0,1);return {rms,level:target===0?previous*.45:previous*.55+target*.45};}
 const definitions={
  idle:{label:'Em ở đây, chủ nhân.',bust:[0],body:[0],step:5000},
  waving:{label:'Chào chủ nhân!',bust:[4,5,6,5,4,7],body:[3],step:330},
  thinking:{label:'Để em suy nghĩ một chút…',bust:[8,9],body:[0],step:1900},
  searching:{label:'Em đang đối chiếu các nguồn…',bust:[8,9],body:[0],step:2100},
  listening:{label:'Em đang chú ý, chủ nhân cứ nói nhé.',bust:[14],body:[5],step:1800},
  speaking:{label:'Em đang trả lời bằng chữ.',bust:[0],body:[0],step:5000},
  waking:{label:'Chủ nhân ơi, dậy thôi ạ!',bust:[12,13],body:[3],step:600},
  clarification:{label:'Chủ nhân nói rõ thêm cho em nhé?',bust:[14],body:[5],step:2000},
  happy:{label:'Xong rồi, chủ nhân.',bust:[11,15],body:[6],step:2000},
  surprised:{label:'Ồ, chủ nhân gọi em sao?',bust:[3,14],body:[5],step:1800},
  error:{label:'Em gặp chút trục trặc. Chủ nhân xem thông báo nhé.',bust:[14],body:[0],step:2000},
  rest:{label:'Em nghỉ một chút nhé, chủ nhân.',bust:[10],body:[2],step:5000},
  salute:{label:'Em đã sẵn sàng, chủ nhân.',bust:[4],body:[4],step:2200},
  pointing:{label:'Chủ nhân xem phía này nhé.',bust:[14],body:[5],step:2200},
  thanks:{label:'Em cảm ơn chủ nhân.',bust:[15],body:[6],step:2200},
  bowing:{label:'Em chào chủ nhân ạ.',bust:[10,15],body:[7],step:2200},
  agree:{label:'Vâng, em hiểu rồi.',bust:[11],body:[6],step:2400},
  disagree:{label:'Em có một điểm cần cân nhắc thêm.',bust:[14],body:[0],step:2400},
  encourage:{label:'Mình làm từng bước nhé, chủ nhân.',bust:[15,11],body:[6],step:2200},
  reading:{label:'Em đang xem kỹ nội dung.',bust:[8],body:[0],step:2600},
  headpat:{label:'Nhẹ nhàng thôi nhé, chủ nhân.',bust:[10],body:[0],step:2400},
  shy:{label:'Em hơi ngại đấy ạ…',bust:[11],body:[0],step:2400},
  hair:{label:'Cảm ơn chủ nhân đã vuốt tóc cho em.',bust:[11],body:[0],step:2400},
  skirt:{label:'Để em chỉnh lại gấu váy nhé.',bust:[14],body:[0],step:2400},
  stretch:{label:'Em vươn vai một chút nhé.',bust:[15],body:[0],step:2400},
  sleepy:{label:'Chúc chủ nhân ngủ ngon.',bust:[10],body:[2],step:2400},
  welcome:{label:'Chào chủ nhân!',bust:[4],body:[3],step:2400},
  playful:{label:'Chủ nhân gọi em ạ?',bust:[11],body:[0],step:2400}
 };
 if(typeof module==='object'&&module.exports)module.exports={cameraClamp,mouthLevel,definitions};
 if(typeof window==='undefined')return;
 const DEMOS={waving:'Chào chủ nhân! Em là Altair. Hôm nay em có thể giúp gì ạ?',speaking:'Chủ nhân, em là Altair. Hôm nay em có thể giúp gì ạ?',waking:'Chủ nhân, sáng rồi ạ. Đến lúc dậy và cùng em bắt đầu một ngày mới nhé.'};
 class Character {
  constructor(root){
   this.root=root;this.pet=document.body.classList.contains('pet-ui');this.stage=root.querySelector('.character-stage');this.caption=root.querySelector('[data-caption]');this.bubble=root.querySelector('[data-bubble]');
   this.world=root.querySelector('[data-world]');this.layers=[...root.querySelectorAll('[data-pose]')];this.mouth=root.querySelector('[data-mouth]');this.blink=root.querySelector('[data-blink]');
   this.rig=window.AltairRig?new window.AltairRig.Rig(this.world,root):null;this.reactionsReady=fetch('assets/reactions.json').then(r=>r.json()).catch(()=>({}));this.interactionId=0;
   this.state='idle';this.mode='body';this.zoom=1;this.pan=0;this.fitted=false;this.index=0;this.activeLayer=0;this.frame=0;this.currentKey='';this.frameTimer=null;this.returnTimer=null;this.blinkTimer=null;this.audioFrame=null;
   this.speechId=0;this.ttsId=null;this.audioAbort=null;this.audioSource=null;this.audioContext=null;this.disposed=false;this.cancelBarrier=Promise.resolve();this.mouthValue=0;
   this.reduce=window.matchMedia('(prefers-reduced-motion: reduce)').matches;
   this.voiceInput=document.getElementById('read-aloud');this.voiceNote=document.getElementById('voice-state');this.motionInput=document.getElementById('reduce-motion');this.zoomInput=document.getElementById('character-zoom');
   this.motionInput.checked=this.reduce;this.motionInput.addEventListener('change',()=>{this.reduce=this.motionInput.checked;this.set(this.state);});
   this.voiceInput.addEventListener('change',()=>{if(!this.voiceInput.checked)this.stopSpeech();});
   root.querySelectorAll('[data-demo]').forEach(b=>b.addEventListener('click',()=>this.demo(b.dataset.demo)));
   document.getElementById('extra-motion').addEventListener('change',e=>{if(e.target.value)this.demo(e.target.value);e.target.value='';});
   document.getElementById('stop-motion').addEventListener('click',()=>{this.stopSpeech();this.set('idle');});
   document.getElementById('show-body').addEventListener('click',()=>{this.mode='body';this.zoom=clamp(this.stage.clientHeight/(this.stage.clientWidth*2),.4,1);this.pan=0;this.applyCamera();this.paint(this.pose()[0],true);});
   document.getElementById('show-portrait').addEventListener('click',()=>{this.mode=this.rig?'body':'bust';this.zoom=this.rig?1.65:1.15;this.pan=0;this.applyCamera();this.paint(this.pose()[0],true);});
   document.getElementById('camera-top').addEventListener('click',()=>{this.pan=0;this.applyCamera();});
   this.zoomInput.addEventListener('input',()=>{this.zoom=Number(this.zoomInput.value);this.applyCamera();});
   if(!this.pet&&!this.rig){this.stage.addEventListener('pointerdown',e=>{if(e.button!==0)return;this.drag={id:e.pointerId,y:e.clientY,start:this.pan};this.stage.setPointerCapture(e.pointerId);this.stage.classList.add('dragging');});
   this.stage.addEventListener('pointermove',e=>{if(this.drag?.id!==e.pointerId)return;this.pan=this.drag.start+e.clientY-this.drag.y;this.applyCamera();});
   const end=e=>{if(this.drag?.id===e.pointerId){this.drag=null;this.stage.classList.remove('dragging');}};this.stage.addEventListener('pointerup',end);this.stage.addEventListener('pointercancel',end);
   this.stage.addEventListener('wheel',e=>{if(this.mode==='body'&&this.stage.clientWidth*2*this.zoom>this.stage.clientHeight){e.preventDefault();this.pan-=e.deltaY;this.applyCamera();}},{passive:false});
   this.stage.addEventListener('keydown',e=>{if(['ArrowUp','ArrowDown','Home','End'].includes(e.key)){e.preventDefault();this.pan=e.key==='Home'?0:e.key==='End'?-10000:this.pan+(e.key==='ArrowUp'?50:-50);this.applyCamera();}});
   }
   this.resizeObserver=new ResizeObserver(()=>this.applyCamera());this.resizeObserver.observe(this.stage);
   this.onVisibility=()=>{if(document.hidden){this.stopSpeech();this.clearTimers();if(this.root.dataset.demo==='true'||['speaking','waking'].includes(this.state))this.state='idle';this.root.classList.add('paused');}else{this.root.classList.remove('paused');this.set(this.state==='speaking'?'idle':this.state);}};document.addEventListener('visibilitychange',this.onVisibility);
   this.applyCamera();this.set('idle');this.updateVoice();
  }
  pose(){return definitions[this.state][this.mode];}
  applyCamera(){if(!this.pet&&!this.fitted&&this.stage.clientHeight>0){this.fitted=true;this.zoom=clamp(this.stage.clientHeight/(this.stage.clientWidth*2),.4,1);}const height=this.stage.clientWidth*(this.mode==='body'?2:1);this.pan=cameraClamp(this.pan,height,this.stage.clientHeight,this.zoom);this.world.style.aspectRatio=this.mode==='body'?'1 / 2':'1 / 1';this.world.style.transform=`translateY(${this.pan}px) scale(${this.zoom})`;this.zoomInput.value=String(this.zoom);this.root.dataset.view=this.mode;this.root.dataset.pan=String(Math.round(this.pan));}
  paint(frame,immediate=false){
   if(this.rig){this.frame=frame;this.root.dataset.frame=String(frame);return;}
   const key=this.mode+':'+frame;if(key===this.currentKey)return;this.currentKey=key;this.frame=frame;
   const next=1-this.activeLayer;const layer=this.layers[next];layer.style.backgroundImage=`url('assets/${this.mode==='body'?'altair-fullbody-v3.png':'altair-atlas-v1.png'}')`;layer.style.backgroundSize=this.mode==='body'?'400% 200%':'400% 400%';layer.style.backgroundPosition=`${frame%4*100/3}% ${Math.floor(frame/4)*(this.mode==='body'?100:100/3)}%`;
   this.layers.forEach((item,i)=>{item.style.transition=immediate?'none':'';item.style.opacity=i===next?'1':'0';});this.activeLayer=next;this.root.dataset.frame=String(frame);
   this.mouth.style.backgroundImage=layer.style.backgroundImage;this.mouth.style.backgroundSize=layer.style.backgroundSize;this.mouth.style.clipPath=this.mode==='body'?'inset(16.1% 47.4% 82.3% 47.4%)':'inset(39.7% 47% 55.3% 47%)';this.mouth.style.transformOrigin=this.mode==='body'?'50% 16.6%':'50% 43%';
  }
  setMouth(level,rms=0){
   this.rig?.setMouth(level);this.mouthValue=level;const open=level>.035;const frame=open?1:0;this.mouth.style.backgroundPosition=`${frame*100/3}% 0%`;this.mouth.style.opacity=(this.audioSource||open)&&this.frame===0?'1':'0';this.mouth.style.transform='none';this.root.dataset.mouth=open?'open':'closed';this.root.dataset.level=level.toFixed(3);
  }
  clearTimers(){clearTimeout(this.frameTimer);clearTimeout(this.returnTimer);clearTimeout(this.blinkTimer);clearTimeout(this.transitionTimer);this.transitionTimer=null;this.frameTimer=this.returnTimer=this.blinkTimer=null;this.blink.style.opacity='0';}
  set(name,{text,duration=0}={}){if(this.disposed||!definitions[name])return false;this.clearTimers();const previous=this.state;this.state=name;this.rig?.setState(name);this.index=0;this.root.dataset.state=name;this.root.classList.toggle('reduced',this.reduce);this.caption.textContent=definitions[name].label;if(text)this.bubble.textContent=text;if(previous!==name&&!this.reduce&&!document.hidden&&this.currentKey){this.paint(0,true);this.root.dataset.transition='settling';this.transitionTimer=setTimeout(()=>{this.paint(this.pose()[0],true);delete this.root.dataset.transition;},160);}else this.paint(this.pose()[0],true);if(!this.audioSource)this.setMouth(0);
   if(!document.hidden&&!this.reduce){this.schedule();this.scheduleBlink();}if(duration>0&&!document.hidden)this.returnTimer=setTimeout(()=>this.set('idle'),Math.min(duration,15000));return true;}
  schedule(){if(this.rig||this.disposed||document.hidden||this.reduce||this.audioSource)return;const frames=this.pose();if(frames.length<2)return;this.frameTimer=setTimeout(()=>{this.index=(this.index+1)%frames.length;this.paint(frames[this.index],true);this.schedule();},definitions[this.state].step);}
  scheduleBlink(){if(this.rig||this.reduce||document.hidden||this.disposed||!['idle','speaking','thinking','searching'].includes(this.state)||this.frame!==0)return;this.blinkTimer=setTimeout(()=>{if(this.frame!==0||this.audioSource){this.scheduleBlink();return;}this.paint(this.mode==='body'?2:10,true);this.root.dataset.eyes='closed';this.blinkTimer=setTimeout(()=>{this.paint(0,true);this.root.dataset.eyes='open';this.scheduleBlink();},130);},4200+Math.random()*1800);}
  async updateVoice(){try{const response=await fetch('/api/tts/status');const data=await response.json();this.voiceNote.textContent=data.installed?'Giọng nữ Nhật thay thế · phụ đề Việt · offline. Chưa phải giọng diễn viên Altair.':'Chưa cài giọng Nhật offline.';}catch{this.voiceNote.textContent='Mở Altair để dùng giọng Nhật offline.';}}
  async unlockAudio(){if(!this.audioContext)this.audioContext=new (window.AudioContext||window.webkitAudioContext)();if(this.audioContext.state==='suspended')await this.audioContext.resume();return this.audioContext;}
  stopSpeech(){
   this.speechId++;this.audioAbort?.abort();this.audioAbort=null;if(this.audioFrame)cancelAnimationFrame(this.audioFrame);this.audioFrame=null;
   if(this.audioSource){this.audioSource.onended=null;try{this.audioSource.stop();}catch{}this.audioSource.disconnect();this.audioSource.buffer=null;this.audioSource=null;}this.audioAnalyser?.disconnect();this.audioAnalyser=null;
   this.setMouth(0);const id=this.ttsId;this.ttsId=null;
   if(id)this.cancelBarrier=fetch('/api/tts/stop',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id})}).catch(()=>{});
   this.root.dataset.audio='stopped';return this.cancelBarrier;
  }
  async say(text,{force=false,sample=null,pose='speaking',japanese=null}={}){
   const audioReady=this.voiceInput.checked||force?this.unlockAudio().catch(error=>({error})):null;
   const barrier=this.stopSpeech();const token=this.speechId;await barrier;if(token!==this.speechId||this.disposed||document.hidden)return false;
   const clean=String(text||'').replace(/https?:\/\/\S+/g,'').replace(/\[\d+\]|[*#`]/g,'').slice(0,500);this.bubble.textContent=clean;
   if(!audioReady||!japanese){this.set(pose==='speaking'?'happy':pose,{duration:pose==='waking'?6500:3500});this.caption.textContent='Em đã trả lời bằng chữ, chủ nhân.';return false;}
   this.set(sample?pose:'idle');this.caption.textContent='Em đang chuẩn bị giọng Nhật offline…';this.root.dataset.audio='preparing';const abort=new AbortController();this.audioAbort=abort;
   try{
    const context=await audioReady;if(context.error)throw context.error;if(token!==this.speechId)return false;
    let response;
    if(sample)response=await fetch('assets/'+sample,{signal:abort.signal});
    else{this.ttsId=crypto.randomUUID().replaceAll('-','');response=await fetch('/api/tts',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:japanese,id:this.ttsId,speed:.95}),signal:abort.signal});}
    if(!response.ok){let error;try{error=(await response.json()).error;}catch{}throw Error(error||'Chưa tạo được giọng đọc.');}
    const buffer=await context.decodeAudioData(await response.arrayBuffer());if(token!==this.speechId||document.hidden)return false;this.ttsId=null;this.audioAbort=null;
    const source=context.createBufferSource();source.buffer=buffer;const analyser=context.createAnalyser();analyser.fftSize=512;source.connect(analyser);analyser.connect(context.destination);this.audioSource=source;this.audioAnalyser=analyser;this.set(pose);this.caption.textContent='Giọng Nhật thay thế · phụ đề Việt';this.root.dataset.audio='playing';
    const samples=new Float32Array(analyser.fftSize);let previous=0,last=0;
    const tick=now=>{if(token!==this.speechId||this.audioSource!==source)return;if(now-last>=33){last=now;analyser.getFloatTimeDomainData(samples);const mouth=mouthLevel(samples,previous);previous=mouth.level;this.setMouth(mouth.level,mouth.rms);}this.audioFrame=requestAnimationFrame(tick);};
    source.onended=()=>{if(token!==this.speechId)return;if(this.audioFrame)cancelAnimationFrame(this.audioFrame);this.audioFrame=null;source.disconnect();analyser.disconnect();source.buffer=null;this.audioSource=null;this.audioAnalyser=null;this.setMouth(0);this.root.dataset.audio='ended';this.set('idle');};source.start();this.audioFrame=requestAnimationFrame(tick);return true;
   }catch(error){if(token!==this.speechId||error.name==='AbortError')return false;this.ttsId=null;this.setMouth(0);this.root.dataset.audio='error';this.set('idle');this.caption.textContent=error.message;return false;}
  }
  greet(){return this.say(DEMOS.speaking,{sample:'voice-ja-greeting.wav',japanese:'ご主人様、アルタイルです。今日は何をお手伝いしましょうか。',pose:'waving'});}
  async act(name){const token=++this.interactionId;if(this.interactionBusy)return;const reactions=await this.reactionsReady;if(token!==this.interactionId||this.disposed)return;const r=reactions[name];if(!r){this.set(name,{duration:4500});return;}return this.say(r.vi,{sample:r.file,japanese:r.ja,pose:name});}
  async demo(name){if(!definitions[name])return;this.root.dataset.demo='true';if(['speaking','waking','waving'].includes(name)&&this.voiceInput.checked)this.unlockAudio().catch(()=>{});const barrier=this.stopSpeech();const token=this.speechId;await barrier;if(token!==this.speechId)return;if(name==='waving')return this.greet();if(name==='speaking')return this.say(DEMOS.speaking,{force:true,sample:'voice-ja-greeting.wav',japanese:'ご主人様、アルタイルです。今日は何をお手伝いしましょうか。'});if(name==='waking')return this.say(DEMOS.waking,{sample:'voice-ja-wakeup.wav',japanese:'ご主人様、朝ですよ。そろそろ起きて、一緒に一日を始めましょう。',pose:'waking'});if(['headpat','shy','hair','skirt','stretch','sleepy','thanks','happy'].includes(name))return this.act(name);if(this.mode==='bust'&&['salute','bowing'].includes(name)){this.mode='body';this.zoom=1;this.pan=0;this.applyCamera();}this.set(name,{text:DEMOS[name]||definitions[name].label,duration:name==='rest'?0:5000});this.root.dataset.demo='true';}
  lockDemo(lock){this.interactionBusy=lock;this.root.querySelectorAll('[data-demo]').forEach(b=>b.disabled=lock);document.getElementById('extra-motion').disabled=lock;if(lock)this.root.dataset.demo='false';}
  respond(text,metrics={}){this.root.dataset.demo='false';if(metrics.judgment?.status==='needs_clarification'&&!this.voiceInput.checked)this.set('clarification',{text,duration:5000});else this.say(text,{japanese:metrics.speech_text||null,sample:metrics.speech_sample||null,pose:metrics.speech_sample?'waving':'speaking'});}
  dispose(){this.stopSpeech();this.clearTimers();this.resizeObserver.disconnect();document.removeEventListener('visibilitychange',this.onVisibility);this.audioContext?.close();this.rig?.dispose();this.disposed=true;}
 }
 window.AltairCharacter={Character,definitions,cameraClamp,mouthLevel};const root=document.getElementById('altair-character');if(root&&!document.body.classList.contains('chat-only')){window.altairCharacter=new Character(root);if(window.AltairInteraction)window.altairTouch=new window.AltairInteraction.TouchController(window.altairCharacter);}
 window.addEventListener('pagehide',e=>{if(!e.persisted)window.altairCharacter?.dispose();});
})();
