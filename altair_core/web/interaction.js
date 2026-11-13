(() => {
 'use strict';
 function commandFor(text){
  const q=String(text).replace(/[\s。、！？!?.,]/g,'');
  if(/^(こんにちは|こんばんは|おはよう(?:ございます)?|やっほー)(?:アルタイル)?$/.test(q))return {action:'waving',vi:'Chủ nhân, em là Altair. Hôm nay em có thể giúp gì ạ?'};
  const commands=[[/^(?:手を振って|バイバイ)$/,'waving','Chào chủ nhân!'],[/^(?:起きて|起こして|起こしてください)$/,'waking','Chủ nhân, sáng rồi ạ. Đến lúc dậy và cùng em bắt đầu một ngày mới nhé.'],[/^(?:おやすみ(?:なさい)?|寝て)$/,'sleepy','Chúc chủ nhân ngủ ngon và có những giấc mơ đẹp.'],[/^(?:ありがとう(?:ございます)?|ありがと)$/,'happy','Không có gì đâu, chủ nhân.'],[/^(?:照れて|恥ずかしがって)$/,'shy','Chủ nhân nhìn vậy làm em hơi ngại ạ.'],[/^(?:頭をなでて|なでなで)$/,'headpat','Chủ nhân, hơi nhột đấy ạ. Nhưng em thấy dễ chịu.'],[/^(?:髪をなでて|髪を整えて)$/,'hair','Cảm ơn chủ nhân đã nhẹ nhàng vuốt tóc cho em.'],[/^(?:背伸びして|伸びをして)$/,'stretch','Để em vươn vai một chút nhé.'],[/^(?:敬礼して|敬礼)$/,'salute','Em đã sẵn sàng, chủ nhân.']];
  for(const [pattern,action,vi] of commands)if(pattern.test(q))return {action,vi};return null;
 }
 if(typeof module==='object'&&module.exports)module.exports={commandFor};
 if(typeof window==='undefined')return;
 class TouchController {
  constructor(character){
   this.c=character;this.stage=character.stage;this.drag=null;this.moveNext=false;this.lastReaction=0;this.taps=[];this.clickTimer=null;
   this.stage.addEventListener('pointerdown',e=>this.down(e));this.stage.addEventListener('pointermove',e=>this.move(e));this.stage.addEventListener('pointerup',e=>this.up(e));this.stage.addEventListener('pointercancel',()=>this.reset());
   this.stage.addEventListener('pointerleave',()=>{if(!this.drag)character.rig?.setLook(0,0);});
   this.stage.addEventListener('dblclick',e=>{e.preventDefault();clearTimeout(this.clickTimer);document.dispatchEvent(new CustomEvent('altair:chat'));});
   this.stage.addEventListener('wheel',e=>{if(character.stage.clientWidth*2*character.zoom>character.stage.clientHeight){e.preventDefault();character.pan-=e.deltaY;character.applyCamera();}},{passive:false});
   this.stage.addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();document.dispatchEvent(new CustomEvent('altair:chat'));}if(e.key===' '){e.preventDefault();window.altairListener?.toggle();}if(e.key==='Escape'){this.reset();window.altairListener?.cancel();}});
  }
  point(e){const b=(this.c.rig?.canvas||this.c.world).getBoundingClientRect();return {x:(e.clientX-b.left)/b.width,y:(e.clientY-b.top)/b.height};}
  down(e){
   if(e.button!==0||this.c.interactionBusy)return;
   clearTimeout(this.clickTimer);const p=this.point(e),zone=window.AltairRig.zoneAt(p.x,p.y);
   this.drag={id:e.pointerId,x:e.clientX,y:e.clientY,sx:e.screenX,sy:e.screenY,lastX:e.clientX,zone,moved:false,distance:0,turns:0,sign:0,pan:this.c.pan,window:!!(e.altKey||this.moveNext)};
   this.moveNext=false;if(!e.native)this.stage.setPointerCapture(e.pointerId);this.c.root.dataset.touch=zone;
   window.pywebview?.api.drag_start(e.screenX,e.screenY,e.native?1:(devicePixelRatio||1));
  }
  move(e){
   const p=this.point(e);this.c.rig?.setLook((p.x-.5)*1.4,(p.y-.2)*.8);
   const d=this.drag;if(d?.id!==e.pointerId)return;
   const dx=e.clientX-d.lastX;d.lastX=e.clientX;d.distance+=Math.abs(dx);
   if(Math.hypot(e.clientX-d.x,e.clientY-d.y)>7)d.moved=true;
   if(d.window||(d.zone==='body'&&d.moved&&this.c.pet)){d.window=true;this.stage.classList.add('dragging');window.pywebview?.api.drag_to(e.screenX,e.screenY);return;}
   if(!d.moved)return;
   if(d.zone==='head'){
    const sign=Math.sign(dx);if(sign&&sign!==d.sign&&Math.abs(dx)>1){d.turns++;d.sign=sign;}
    this.c.set(d.turns>5?'shy':'headpat');this.c.rig?.stroke(dx/160);this.c.root.dataset.strokes=String(d.turns);
   }else if(d.zone==='hair'){this.c.set('hair');this.c.rig?.stroke(dx/140);}
   else if(!this.c.pet){this.c.pan=d.pan+e.clientY-d.y;this.c.applyCamera();}
  }
  up(e){
   const d=this.drag;if(d?.id!==e.pointerId)return;this.reset();if(d.window)return;
   const action=d.zone==='head'?(d.turns>5?'shy':'headpat'):d.zone==='hair'?'hair':d.zone==='skirt'?'skirt':d.zone==='boots'?'agree':'waving';
   if(d.moved&&!['head','hair'].includes(d.zone))return;
   this.clickTimer=setTimeout(()=>this.react(action),d.moved?0:270);
  }
  react(action){
   if(this.c.interactionBusy)return;const now=performance.now();if(now-this.lastReaction<1400){this.c.rig?.setState(action);return;}
   this.lastReaction=now;this.c.root.dataset.lastInteraction=action;
   if(action==='headpat'){this.taps=this.taps.filter(t=>now-t<6500);this.taps.push(now);if(this.taps.length>=3)action='shy';}
   this.c.demo(action);
  }
  reset(){if(this.drag)try{this.stage.releasePointerCapture(this.drag.id);}catch{}this.drag=null;this.stage.classList.remove('dragging');}
 }
 window.altairNativePointer=event=>{
  const touch=window.altairTouch;if(!touch)return;
  const c=touch.c,stage=touch.stage;
  const target=document.elementFromPoint(event.x,event.y);
  if(target?.closest('#pet-menu')){if(event.kind==='up')target.closest('button')?.click();return;}
  if(event.button===2){if(event.kind==='up')stage.dispatchEvent(new MouseEvent('contextmenu',{bubbles:true,cancelable:true,clientX:event.x,clientY:event.y}));return;}
  if(event.kind==='double'){clearTimeout(touch.clickTimer);touch.reset();document.dispatchEvent(new CustomEvent('altair:chat'));return;}
  const e={button:0,pointerId:991,clientX:event.x,clientY:event.y,screenX:event.sx,screenY:event.sy,altKey:!!event.alt,native:true};
  if(event.kind==='down')touch.down(e);if(event.kind==='move')touch.move(e);if(event.kind==='up')touch.up(e);
 };
 let traces=0;for(const type of ['pointerdown','pointerup','dblclick','contextmenu'])document.addEventListener(type,e=>{if(traces++<24)window.pywebview?.api?.trace?.({type:e.type,x:e.clientX,y:e.clientY,target:e.target?.id||e.target?.className||e.target?.tagName});},true);
 window.AltairInteraction={TouchController,commandFor};
})();
