/* Native bridge only moves this Altair window; no arbitrary OS commands. */
(() => {
 'use strict';
 const pet=window.altairCharacter,stage=pet.stage,menu=document.getElementById('pet-menu'),dock=document.getElementById('pet-dock');
 const native=()=>window.pywebview?.api;
 let drag=null,clickTimer=null,bubbleTimer=null,rest=false;
 const region=()=>{const elements=[menu,dock,document.querySelector('.chat-panel'),pet.bubble];const rects=elements.filter(el=>getComputedStyle(el).display!=='none').map(el=>{const r=el.getBoundingClientRect();return [r.x,r.y,r.width,r.height];});native()?.interactive(rects,[window.innerWidth,window.innerHeight]);};
 const bubble=(ms=8000)=>{clearTimeout(bubbleTimer);document.body.dataset.bubble='true';region();bubbleTimer=setTimeout(()=>{document.body.dataset.bubble='false';region();},ms);};
 function chat(open){menu.hidden=true;if(native()){document.body.dataset.chat='false';region();if(open){pet.unlockAudio().catch(()=>{});native().chat();}return;}document.body.dataset.chat=String(open);region();if(open)document.getElementById('question').focus();}
 document.getElementById('close-pet-chat').onclick=()=>chat(false);document.addEventListener('altair:chat',()=>chat(true));
 stage.setAttribute('aria-label','Altair 2D có khớp: xoa đầu, vuốt tóc, chạm váy; kéo thân để di chuyển; nhấn đúp trò chuyện; chuột phải mở menu');
 stage.addEventListener('contextmenu',e=>{e.preventDefault();clearTimeout(clickTimer);menu.hidden=!menu.hidden;region();});
 document.addEventListener('keydown',e=>{if(e.key==='Escape'){chat(false);menu.hidden=true;pet.stopSpeech();window.altairListener?.cancel();pet.set('idle');region();}});
 const petAction=async e=>{const action=e.target.closest('[data-pet]')?.dataset.pet;if(!action)return;menu.hidden=true;
  if(action==='menu'){menu.hidden=false;region();return;}
  if(action==='chat')return chat(true);
  if(action==='listen'){window.altairListener?.toggle();region();return;}
  if(action==='move'){window.altairTouch.moveNext=true;pet.bubble.textContent='Chủ nhân kéo em đến vị trí muốn nhé. Cũng có thể kéo phần thân.';}
  if(['pat','shy','hair','skirt','stretch'].includes(action))pet.demo(action==='pat'?'headpat':action);
  if(action==='wave')pet.demo('waving');
  if(action==='wake')pet.demo('waking');
  if(action==='rest'){rest=!rest;pet.stopSpeech();pet.set(rest?'rest':'idle',{text:rest?'Em nghỉ một chút nhé, chủ nhân.':'Em ở đây, chủ nhân.'});}
  if(action==='mute'){pet.voiceInput.checked=!pet.voiceInput.checked;if(!pet.voiceInput.checked)pet.stopSpeech();pet.bubble.textContent=pet.voiceInput.checked?'Em đã bật giọng Nhật, chủ nhân.':'Em đã tắt giọng, chủ nhân.';}
  if(action==='studio'){if(native())native().studio();else window.open('/','_blank','noopener');}
  if(action==='close'){window.altairListener?.cancel();pet.dispose();if(native())native().close();else window.close();return;}
  bubble();region();
 };
 menu.addEventListener('click',petAction);dock.addEventListener('click',petAction);
 new MutationObserver(()=>{if(pet.bubble.textContent.trim())bubble(pet.root.dataset.audio==='playing'?45000:12000);}).observe(pet.bubble,{childList:true,characterData:true,subtree:true});
 new MutationObserver(()=>{if(pet.root.dataset.audio==='ended')bubble(10000);}).observe(pet.root,{attributes:true,attributeFilter:['data-audio']});
 document.addEventListener('pywebviewready',()=>{region();});
 pet.zoom=1;pet.pan=0;pet.applyCamera();
})();
