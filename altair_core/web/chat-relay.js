/* An opaque, on-demand chat window drives the existing transparent character. */
(() => {
 const only=document.body.classList.contains('chat-only');
 const channel=typeof BroadcastChannel==='function'?new BroadcastChannel('altair-local-avatar'):null;
 function receive(kind,data={}){
  const c=window.altairCharacter;if(!c||only)return;
  if(kind==='state')c.set(data.name,{text:data.text});
  if(kind==='respond')c.respond(data.text,data.metrics||{});
  if(kind==='demo')c.demo(data.name);
  if(kind==='stop'){c.stopSpeech();c.set('idle');}
  if(kind==='busy')c.lockDemo(!!data.value);
 }
 if(!only){window.altairFromChat=receive;if(channel&&document.body.classList.contains('pet-ui'))channel.onmessage=e=>receive(e.data.kind,e.data.data);return;}
 const status=text=>{const el=document.getElementById('chat-status');if(el)el.textContent=String(text||'');};
 let queue=Promise.resolve();
 const send=(kind,data={})=>{if(window.pywebview?.api?.relay){queue=queue.catch(()=>{}).then(()=>window.pywebview.api.relay(kind,data)).catch(()=>status('Chưa kết nối được nhân vật.'));return queue;}channel?.postMessage({kind,data});return Promise.resolve();};
 const textProxy={set textContent(text){status(text);},get textContent(){return document.getElementById('chat-status')?.textContent||'';}};
 window.altairCharacter={root:document.getElementById('altair-character'),bubble:textProxy,caption:textProxy,interactionBusy:false,
  unlockAudio:async()=>{},stopSpeech:()=>send('stop'),set:(name,options={})=>send('state',{name,text:options.text}),
  respond:(text,metrics)=>{status('Câu trả lời đã gửi tới Altair.');return send('respond',{text,metrics});},
  dispose(){},demo:name=>send('demo',{name}),lockDemo(value){this.interactionBusy=value;send('busy',{value});}
 };
 window.addEventListener('pagehide',()=>{window.altairListener?.cancel();send('busy',{value:false});channel?.close();});
})();
