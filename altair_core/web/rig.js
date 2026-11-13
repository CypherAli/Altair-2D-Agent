/* Altair 2D cutout skeleton.
   FK torso/head/hair, two-bone IK arms with soft joint patches, blended pose
   transitions with follow-through, and spring secondary motion. No libraries. */
(() => {
 'use strict';
 const clamp=(n,a,b)=>Math.min(b,Math.max(a,n));
 const mix=(a,b,t)=>a+(b-a)*t;
 const TAU=Math.PI*2;
 const wrap=a=>{a=(a+Math.PI)%TAU;return a<0?a+TAU-Math.PI:a-Math.PI;};
 const easeOut=t=>1-(1-t)*(1-t)*(1-t);
 const easeInOut=t=>t<.5?4*t*t*t:1-Math.pow(-2*t+2,3)/2;
 const NECK_X=150,NECK_Y=126,BODY_X=150,BODY_Y=238,L1=60,L2=74;
 const SHOULDERS=[{x:97,y:151},{x:203,y:151}];
 function solveArm(x,y,l1=60,l2=74,side=1){
  const d=clamp(Math.hypot(x,y),Math.abs(l1-l2)+.1,l1+l2-.1);
  const bend=side*Math.acos(clamp((d*d-l1*l1-l2*l2)/(2*l1*l2),-1,1));
  return {shoulder:Math.atan2(y,x)-Math.atan2(l2*Math.sin(bend),l1+l2*Math.cos(bend))-Math.PI/2,elbow:bend};
 }
 function zoneAt(x,y){if(y<.23&&x>.29&&x<.71)return 'head';if(y>.22&&y<.78&&(x<.28||x>.72))return 'hair';if(y>.4&&y<.82&&x>.18&&x<.82)return 'skirt';if(y>=.82)return 'boots';return 'body';}
 const names=['idle','waving','thinking','searching','listening','speaking','waking','clarification','happy','surprised','error','rest','salute','pointing','thanks','bowing','agree','disagree','encourage','reading','headpat','shy','hair','skirt','stretch','sleepy','welcome','playful'];
 /* A point fixed to the head, so gestures stay on the face while the head moves. */
 function headPoint(p,x,y){
  const c=Math.cos(p.head),s=Math.sin(p.head);
  return {x:NECK_X+p.headX+x*c-y*s,y:NECK_Y+p.headY+x*s+y*c};
 }
 function poseAt(state,t,look={x:0,y:0}){
  const s=Math.sin,c=Math.cos;
  const p={body:look.x*.012,hip:look.x*.005,head:look.x*.035,headY:s(t*1.7)*.5,headX:look.x*2,
   skirt:s(t*1.4)*.008,leftX:90+s(t*.55)*.8,leftY:282+s(t*.55+1.1)*1.8,rightX:210+s(t*.55+.9)*.8,rightY:282+s(t*.55+2.2)*1.8,leftHand:0,rightHand:0,wristL:0,wristR:0,
   expression:0,blush:0,hair:0,scaleY:1,breath:s(t*1.1)*.5};
  switch(state){
   case 'waving':case 'welcome':p.leftX=68+s(t*7)*9;p.leftY=74+c(t*7)*6;p.leftHand=1;p.wristL=-.12;p.head=.035*s(t*2);p.blush=.15;break;
   case 'waking':p.leftX=64+s(t*8)*9;p.leftY=132+c(t*8)*16;p.rightX=236-s(t*8)*9;p.rightY=132-c(t*8)*16;p.leftHand=p.rightHand=1;p.headY=3+s(t*4)*2;p.body=.018*s(t*4);p.head=.03*s(t*4);p.hair=.04*s(t*4);break;
   case 'thinking':p.head=-.05;p.headY=1+s(t*2)*.8;p.leftX=146+s(t*1.6)*1.4;p.leftY=206+s(t*1.6)*1.4;p.leftHand=1;p.wristL=-.5;break;
   case 'searching':p.headY=1+Math.sin(t*1.3)*1.2;p.head=-.03;p.leftX=116;p.leftY=236;p.leftHand=1;p.wristL=-.35;p.rightX=190;p.rightY=244;p.headX=3;break;
   case 'listening':p.head=-.045;p.headY=1;p.leftX=112;p.leftY=258;p.rightX=194;p.rightY=252;p.body=-.008;break;
   case 'clarification':p.leftX=84;p.leftY=214;p.leftHand=1;p.wristL=-.35;p.head=-.055;p.headY=-.5;break;
   case 'error':p.leftX=84;p.leftY=224;p.leftHand=1;p.head=-.045;p.rightX=216;p.rightY=272;break;
   case 'speaking':p.leftX=94+s(t*2)*5;p.leftY=262+c(t*2)*3;p.rightX=206-s(t*2)*5;p.rightY=262-c(t*2)*3;p.head=.018*s(t*1.8);break;
   case 'happy':p.leftX=136;p.leftY=228;p.rightX=164;p.rightY=228;p.wristL=p.wristR=.25;p.headY=-1+2*s(t*3);p.blush=.35;break;
   case 'surprised':p.leftX=68;p.leftY=196;p.rightX=232;p.rightY=196;p.leftHand=p.rightHand=1;p.expression=3;p.headY=-2;p.blush=.2;break;
   case 'rest':case 'sleepy':p.expression=1;p.head=.075;p.headY=3;p.leftX=112;p.leftY=286;p.rightX=188;p.rightY=286;p.scaleY=.99;p.wristL=p.wristR=.2;break;
   case 'salute':{p.head=-.03;const q=headPoint(p,-30,-64);p.leftX=q.x;p.leftY=q.y;p.leftHand=1;p.wristL=-.35;break;}
   case 'pointing':p.rightX=272;p.rightY=172;p.rightHand=1;p.wristR=.1;p.head=-.04;p.headX=4;break;
   case 'thanks':p.leftX=138;p.leftY=232;p.rightX=162;p.rightY=232;p.wristL=p.wristR=.3;p.headY=4;p.head=.045;p.blush=.2;break;
   case 'bowing':p.leftX=96;p.leftY=272;p.rightX=204;p.rightY=272;p.headY=7;p.head=.08;p.expression=1;p.body=.025;p.scaleY=.97;break;
   case 'agree':p.headY=2+3*s(t*5);p.head=.01*s(t*5);p.leftX=92;p.leftY=278;p.rightX=208;p.rightY=278;break;
   case 'disagree':p.head=.095*s(t*4);p.headX=3*s(t*4);p.leftX=94;p.leftY=276;p.rightX=206;p.rightY=276;p.wristL=p.wristR=-.15;break;
   case 'encourage':p.leftX=104;p.leftY=268;p.rightX=150;p.rightY=236;p.rightHand=1;p.rightY+=s(t*1.4)*2;p.blush=.2;p.head=-.025;break;
   case 'reading':p.headY=3;p.head=.055;p.leftX=140;p.leftY=226;p.rightX=160;p.rightY=226;p.leftHand=1;p.wristL=p.wristR=-.35;break;
   case 'headpat':p.expression=1;p.head=.09*s(t*3);p.headY=2;p.blush=.4;p.hair=.04*s(t*3);p.leftX=104;p.leftY=272;p.rightX=196;p.rightY=272;p.wristL=p.wristR=.15;break;
   case 'shy':p.expression=2;p.blush=.7;p.head=-.12;p.headX=-3;p.leftX=137;p.leftY=207;p.rightX=163;p.rightY=207;p.wristL=p.wristR=.35;p.body=-.017;break;
   case 'hair':p.blush=.25;p.head=.06;p.hair=.09*s(t*3);p.leftX=116;p.leftY=246;p.rightX=184;p.rightY=246;p.wristL=p.wristR=.1;break;
   case 'skirt':p.headY=4;p.head=.04;p.blush=.4;p.leftX=126+3*s(t*4);p.leftY=282;p.rightX=174-3*s(t*4);p.rightY=282;p.skirt=.012*s(t*3);break;
   case 'stretch':p.leftX=78+4*s(t*2);p.leftY=58;p.rightX=222-4*s(t*2);p.rightY=58;p.leftHand=p.rightHand=1;p.headY=-3;p.body=.014*s(t*2);p.expression=1;p.wristL=p.wristR=-.25;break;
   case 'playful':p.leftX=80;p.leftY=214;p.rightX=220;p.rightY=214;p.leftHand=p.rightHand=1;p.head=.075*s(t*4);p.blush=.5;p.body=.012*s(t*4);break;
  }
  /* Standing weight: people rest on one leg, hold it, then change sides. A
     tanh-warped sine holds each side for a few beats instead of gliding.
     The pelvis travels toward the loaded leg, the ribcage counters slightly,
     and the head keeps the horizon steady (balance, not a swaying statue). */
  const shift=Math.tanh(s(t*.16)*2.4);
  p.body+=shift*.006+s(t*.7)*.002;
  p.hip+=shift*1.6+s(t*.7)*.35;
  p.skirt+=shift*.006;
  p.head-=p.body*.55;
  p.shift=shift;
  return p;
 }
 if(typeof module==='object'&&module.exports)module.exports={solveArm,zoneAt,poseAt,names};
 if(typeof window==='undefined')return;
 const rects=[
  [57,18,180,263],[334,18,180,263],[611,18,180,263],[886,18,180,263],
  [44,308,207,250],[301,323,242,261],[565,284,196,319],[905,284,196,319],
  [101,603,96,223],[369,603,102,223],[622,611,144,210],[924,604,137,204],
  [95,847,101,232],[366,847,102,232],[623,858,130,213],[924,853,94,206],
  [108,1098,74,282],[385,1098,74,282],[650,1199,83,70],[940,1202,58,61]
 ];
 const PIXEL=1.5,TORSO_BOX=[88,116,124,127],SLEEVE_BOX=[-19,-9,38,81];
 /* Channels are eased in groups so hips lead, arms follow, head settles last. */
 const GROUPS={body:{delay:0,dur:.20,w:11},arms:{delay:.04,dur:.24,w:20},head:{delay:.07,dur:.26,w:12},face:{delay:0,dur:.10,w:30}};
 class Rig {
  constructor(world,root){
   this.world=world;this.root=root;this.canvas=document.createElement('canvas');this.canvas.className='joint-canvas';this.canvas.setAttribute('aria-hidden','true');this.canvas.width=450;this.canvas.height=900;world.querySelector('.character-rig').append(this.canvas);this.ctx=this.canvas.getContext('2d',{alpha:true,willReadFrequently:false});
   this.state='idle';this.since=performance.now();this.last=0;this.lastDraw=0;this.blendStart=0;this.look={x:0,y:0};this.mouth=0;this.disposed=false;this.frames=0;this.lastMask=0;this.blinkAt=performance.now()+3800;this.blinkEnd=0;this.joints={};
   const base=poseAt('idle',0,this.look);
   this.cur={};   for(const key of ['body','hip','head','headY','headX','skirt','scaleY','blush','wristL','wristR','breath','shift'])this.cur[key]=base[key];
   this.hands=[base.leftHand,base.rightHand];this.expression=base.expression;this.hairAngle=base.hair;
   this.arms=[0,1].map(i=>{
    const target=i?[base.rightX,base.rightY]:[base.leftX,base.leftY],sh=SHOULDERS[i];
    const dx=target[0]-sh.x,dy=target[1]-sh.y;
    return {ang:Math.atan2(dy,dx),rad:Math.hypot(dx,dy),wrist:i?base.wristR:base.wristL,bend:i?1:-1};
   });
   this.from={pose:{...this.cur},arms:this.arms.map(a=>({ang:a.ang,rad:a.rad,wrist:a.wrist}))};
   this.hair=[{x:0,v:0},{x:0,v:0}];this.stroking=0;
   this.image=new Image();
   this.image.onload=()=>{this.ready=true;this.buildPatches();root.classList.add('rig-active');root.dataset.renderer='joint-2d';this.draw(performance.now(),0);};
   this.image.src='assets/altair-rig-parts-v1.png';
   this.tick=this.tick.bind(this);this.raf=requestAnimationFrame(this.tick);
  }
  setState(name){if(!names.includes(name)||name===this.state)return;this.from={pose:{...this.cur},arms:this.arms.map(a=>({ang:a.ang,rad:a.rad,wrist:a.wrist}))};this.blendStart=performance.now();this.state=name;this.since=performance.now();this.root.dataset.rigMotion=name;}
  setMouth(value){this.mouth=clamp(value,0,1);}
  setLook(x,y){this.look={x:clamp(x,-1,1),y:clamp(y,-1,1)};}
  stroke(amount){this.stroking=clamp(amount,-.15,.15);}
  part(index,x,y,w,h){const r=rects[index];this.ctx.drawImage(this.image,...r,x,y,w,h);}
  bone(x,y,angle,draw){const c=this.ctx;c.save();c.translate(x,y);c.rotate(angle);draw();c.restore();}
  /* Contact shadow. Meant to be drawn with 'source-atop' so it only darkens
     artwork that is already there and never paints a blob in empty space. */
  softShadow(x,y,rx,ry,alpha){
   const c=this.ctx,r=Math.max(rx,ry),g=c.createRadialGradient(0,0,r*.12,0,0,r);
   g.addColorStop(0,`rgba(6,9,14,${alpha})`);g.addColorStop(.6,`rgba(6,9,14,${alpha*.45})`);g.addColorStop(1,'rgba(6,9,14,0)');
   c.save();c.translate(x,y);c.scale(rx/r,ry/r);c.fillStyle=g;c.fillRect(-r,-r,r*2,r*2);c.restore();
  }
  /* One lock of long hair drawn as a chain of bands, so it bends along its
     length instead of swinging as a single stiff plank. Source aspect kept. */
  /* The lock keeps the artwork's exact aspect. A second, smaller copy is
     dropped behind it so the tips continue into a long drape: the front lock
     hides the rear copy's thick root, so no seam and no stretching. */
  hairLock(i){
   const c=this.ctx,p=this.cur,w=126,h=205,base=p.head*.55+this.hair[i].x;
   /* Root rides on the skull: when the head turns, the lock turns with it and
     the spring only adds lag. At face zoom a loose root would open a gap. */
   const root=headPoint(p,i?44:-44,-26);
   const drop=h*.62,head={x:root.x,y:root.y,rot:base,w,h};
   const tail={x:head.x-Math.sin(base)*drop+(i?4:-4),y:head.y+Math.cos(base)*drop,rot:base*1.8,w:w*.94,h:h*.94};
   for(const lock of [tail,head]){
    c.save();c.translate(lock.x,lock.y);c.rotate(lock.rot);
    this.part(6+i,-lock.w/2,-1,lock.w,lock.h+2);
    c.restore();
   }
  }
  /* Circular crop of a sprite region with a feathered rim: covers the flat end
     of a sleeve and the step where forearm artwork meets it. */
  patch(rect,box,cx,cy,r){
   const size=Math.max(8,Math.round(r*2*PIXEL)),cv=document.createElement('canvas');cv.width=cv.height=size;
   const g=cv.getContext('2d');
   const sx=rect[0]+((cx-r-box[0])/box[2])*rect[2],sy=rect[1]+((cy-r-box[1])/box[3])*rect[3];
   const sw=(2*r/box[2])*rect[2],sh=(2*r/box[3])*rect[3];
   g.drawImage(this.image,sx,sy,sw,sh,0,0,size,size);
   g.globalCompositeOperation='destination-in';
   const grad=g.createRadialGradient(size/2,size/2,size*.2,size/2,size/2,size*.5);
   grad.addColorStop(0,'rgba(0,0,0,1)');grad.addColorStop(.66,'rgba(0,0,0,1)');grad.addColorStop(1,'rgba(0,0,0,0)');
   g.fillStyle=grad;g.fillRect(0,0,size,size);
   return cv;
  }
  /* Pre-render a sprite region with a feathered lower rim, so two rigid parts
     meeting at a joint dissolve into each other instead of showing a cut. */
  slice(x,y,w,h,bottom=.3,top=0,scale=.75){
   const cv=document.createElement('canvas');cv.width=Math.max(1,Math.round(w*scale));cv.height=Math.max(1,Math.round(h*scale));
   const g=cv.getContext('2d');
   g.drawImage(this.image,x,y,w,h,0,0,cv.width,cv.height);
   g.globalCompositeOperation='destination-in';
   const grad=g.createLinearGradient(0,0,0,cv.height);
   if(top>0){grad.addColorStop(0,'rgba(0,0,0,0)');grad.addColorStop(top,'rgba(0,0,0,1)');}
   else grad.addColorStop(0,'rgba(0,0,0,1)');
   grad.addColorStop(1-bottom,'rgba(0,0,0,1)');grad.addColorStop(1,'rgba(0,0,0,0)');
   g.fillStyle=grad;g.fillRect(0,0,cv.width,cv.height);
   return cv;
  }
  buildPatches(){
   this.sleeves=[this.slice(rects[8][0],rects[8][1],rects[8][2],rects[8][3],.24,.05),this.slice(rects[12][0],rects[12][1],rects[12][2],rects[12][3],.24,.05)];
   this.patches={
    /* Covers the flat top of the sleeve, so the arm leaves the body from under
       the epaulette instead of ending in a visible cut. */
    shoulder:[this.patch(rects[4],TORSO_BOX,95,142,13),this.patch(rects[4],TORSO_BOX,205,142,13)],
    neck:this.patch(rects[4],TORSO_BOX,150,130,14),
    sleeve:[this.patch(rects[8],SLEEVE_BOX,0,0,13),this.patch(rects[12],SLEEVE_BOX,0,0,13)]
   };
  }
  tick(now){
   if(this.disposed)return;this.raf=requestAnimationFrame(this.tick);
   if(document.hidden||!this.ready){this.last=now;return;}
   const reduced=this.root.classList.contains('reduced'),fps=reduced?10:this.state==='idle'?30:60;
   if(now-this.lastDraw<1000/fps)return;
   const dt=Math.min(.05,Math.max(.001,(now-(this.last||now))/1000));this.last=now;this.lastDraw=now;
   this.step(now,dt,reduced);this.draw(now,dt);this.frames++;this.root.dataset.rigFrames=String(this.frames);
  }
  step(now,dt,reduced){
   const t=(now-this.since)/1000,target=poseAt(this.state,reduced?0:t,this.look),elapsed=(now-this.blendStart)/1000,from=this.from.pose;
   const p=(group)=>{const g=GROUPS[group];return easeOut(clamp((elapsed-g.delay)/g.dur,0,1));};
   const body=p('body'),arms=p('arms'),head=p('head'),face=p('face'),bodyK=1-Math.exp(-GROUPS.body.w*dt);
   this.cur.body+=((mix(from.body,target.body,body))-this.cur.body)*(1-Math.exp(-GROUPS.body.w*dt));
   this.cur.hip+=((mix(from.hip,target.hip,body))-this.cur.hip)*(1-Math.exp(-GROUPS.body.w*dt));
   this.cur.skirt+=((mix(from.skirt,target.skirt,body))-this.cur.skirt)*(1-Math.exp(-GROUPS.body.w*dt));
   this.cur.scaleY+=((mix(from.scaleY,target.scaleY*(1+target.breath*.003),body))-this.cur.scaleY)*(1-Math.exp(-GROUPS.body.w*dt));
   this.cur.breath+=((mix(from.breath,target.breath,body))-this.cur.breath)*bodyK;
   this.cur.shift+=((mix(from.shift,target.shift,body))-this.cur.shift)*bodyK;
   const headK=1-Math.exp(-GROUPS.head.w*dt);
   this.cur.head+=(mix(from.head,target.head,head)-this.cur.head)*headK;
   this.cur.headY+=(mix(from.headY,target.headY-target.breath*.5,head)-this.cur.headY)*headK;
   this.cur.headX+=(mix(from.headX,target.headX,head)-this.cur.headX)*headK;
   this.cur.blush+=(mix(from.blush,target.blush,face)-this.cur.blush)*(1-Math.exp(-GROUPS.face.w*dt));
   this.expression=clamp(Math.round(target.expression),0,3);this.hairAngle=target.hair;
   this.hands=[target.leftHand,target.rightHand];
   const armK=1-Math.exp(-GROUPS.arms.w*dt),wristK=1-Math.exp(-10*dt);
   for(let i=0;i<2;i++){
    const arm=this.arms[i],sh=SHOULDERS[i],tx=i?target.rightX:target.leftX,ty=i?target.rightY:target.leftY;
    const goalAng=Math.atan2(ty-sh.y,tx-sh.x),goalRad=Math.hypot(tx-sh.x,ty-sh.y);
    const blendAng=this.from.arms[i].ang+wrap(goalAng-this.from.arms[i].ang)*arms;
    const blendRad=mix(this.from.arms[i].rad,goalRad,arms);
    arm.ang+=wrap(blendAng-arm.ang)*armK;
    arm.rad+=(clamp(blendRad,Math.abs(L1-L2)+.5,L1+L2-.5)-arm.rad)*armK;
    arm.wrist+=((i?target.wristR:target.wristL)-arm.wrist)*wristK;
    /* Keep the elbow on the outboard side of the shoulder-wrist line; without
       this a raised hand folds the sleeve across the face. Hysteresis stops
       the elbow flipping when the wrist crosses the shoulder. */
    const reach=arm.rad,dir=arm.ang,dx=Math.cos(dir)*reach,dy=Math.sin(dir)*reach;
    const elbow=s=>{const a=solveArm(dx,dy,L1,L2,s),t=a.shoulder+Math.PI/2;return {x:sh.x+L1*Math.cos(t),y:sh.y+L1*Math.sin(t)};};
    /* Outboard, but an elbow above the shoulder is penalised: real elbows sit
       at or below the joint unless the arm is folded over the head. */
    const score=s=>{const e=elbow(s);return (i?e.x:-e.x)-Math.max(0,sh.y-6-e.y)*2.5;};
    const other=-arm.bend;
    if(score(other)>score(arm.bend)+4)arm.bend=other;
   }
   /* Hair follows the head with drag, not with its own unrelated sine. */
   for(let i=0;i<2;i++){
    const spring=this.hair[i],wanted=(reduced?0:Math.sin(now/950+i)*.016)+this.hairAngle+this.stroking*(i?-1:1)*.6;
    spring.v+=(wanted-spring.x)*70*dt;spring.v*=Math.exp(-9*dt);spring.x+=spring.v*dt;
   }
   this.stroking*=Math.exp(-dt*3);
  }
  arm(side,lift=0){
   const i=side<0?0:1,arm=this.arms[i],isLeft=side<0,sh={x:SHOULDERS[i].x,y:SHOULDERS[i].y+lift};
   const tx=sh.x+Math.cos(arm.ang)*arm.rad,ty=sh.y+Math.sin(arm.ang)*arm.rad;
   const angles=solveArm(tx-sh.x,ty-sh.y,L1,L2,arm.bend),base=isLeft?8:12,c=this.ctx;
   this.joints[isLeft?'left':'right']={shoulder:angles.shoulder,elbow:angles.elbow,wristX:tx,wristY:ty};
   this.bone(sh.x,sh.y,angles.shoulder,()=>{
    /* Bracer under the sleeve: the cloth covers the cuff edge at the elbow, so
       the joint reads as folded fabric instead of two capped tubes. */
    this.bone(0,60,angles.elbow,()=>this.part(base+1,-23,-9,46,88));
    if(this.sleeves)c.drawImage(this.sleeves[i],-19,-9,38,81);else this.part(base,-19,-9,38,81);
    /* Round sleeve head turning with the arm: the flat top of the artwork can
       never poke out above the shoulder when the arm is raised. */
    if(this.patches){const cap=this.patches.sleeve[i],r=14;c.drawImage(cap,-r,-r,r*2,r*2);}
    this.bone(0,60,angles.elbow,()=>this.bone(0,74,arm.wrist,()=>{
     if(this.hands[i]){c.rotate(Math.PI);this.part(base+2,-19,-51,38,58);}else this.part(base+3,-15,-7,30,53);
    }));
   });
  }
  draw(now){
   const c=this.ctx,p=this.cur;c.setTransform(PIXEL,0,0,PIXEL,0,0);c.clearRect(0,0,300,600);c.imageSmoothingEnabled=true;c.imageSmoothingQuality='high';
   c.save();c.translate(BODY_X,BODY_Y);c.rotate(p.body);c.scale(1,p.scaleY);c.translate(-BODY_X,-BODY_Y);
   this.hairLock(0);this.hairLock(1);
   /* Loaded leg stands straighter and the free knee softens, so the pelvis can
     actually travel over one foot instead of sliding both. */
   const load=p.shift||0;
   this.bone(128+p.hip,471-load*1.2,-p.body*.7+Math.sin(now/1500)*.006+load*.012,()=>this.part(16,-19,-4,38,128));
   this.bone(172-p.hip,471+load*1.2,-p.body*.7-Math.sin(now/1500)*.006-load*.012,()=>this.part(17,-19,-4,38,128));
   this.bone(150,231,p.skirt,()=>this.part(5,-99,2,198,265));
   this.part(4,88,116,124,127);
   /* Seams read as cut paper without contact shadow; seat every overlap. */
   c.save();c.globalCompositeOperation='source-atop';
   this.softShadow(150,247,48,11,.22);
   this.softShadow(150,128,34,13,.2);
   this.softShadow(116,160,20,12,.14);this.softShadow(184,160,20,12,.14);
   this.softShadow(100,176,11,15,.16);this.softShadow(200,176,11,15,.16);
   c.restore();
   const reduced=this.root.classList.contains('reduced');
   if(!reduced&&now>=this.blinkAt){this.blinkEnd=now+105;this.blinkAt=now+3900+Math.random()*2400;}
   const eyeClosed=this.expression===1||now<this.blinkEnd,face=eyeClosed?1:this.expression;
   if(this.patches)c.drawImage(this.patches.neck,150-14,130-14,28,28);
   this.bone(NECK_X+p.headX,NECK_Y+p.headY,p.head,()=>{
    c.scale(1-Math.abs(this.look.x)*.03,1);this.part(face,-43,-121,86,126);
    if(p.blush>0){const grad=c.createRadialGradient(-14,-25,1,-14,-25,8);grad.addColorStop(0,`rgba(230,92,110,${p.blush*.28})`);grad.addColorStop(1,'rgba(230,92,110,0)');c.fillStyle=grad;c.fillRect(-23,-34,18,18);c.save();c.scale(-1,1);c.fillRect(-23,-34,18,18);c.restore();}
    if(this.mouth>.04){const h=3+this.mouth*4;this.part(this.mouth>.65?19:18,-4,-19-h/2,8,h);}
   });
   /* Arms sit above the head so a hand on the chin or temple stays visible. */
   /* Ribcage rises with the breath, so the shoulder sockets lift with it and
     the ribcage on the exhale settles back down. */
   const lift=p.breath*1.8;
   this.arm(-1,lift);this.arm(1,lift);
   if(this.patches){
    /* Epaulettes/shoulder cloth drawn over the sleeve top so a raised arm
       emerges from under the shoulder instead of cutting off flat. */
    const r=14,capX=[96,204],capY=139+lift;
    for(let i=0;i<2;i++)c.drawImage(this.patches.shoulder[i],capX[i]-r,capY-r,r*2,r*2);
   }
   c.restore();
   this.root.dataset.rigBones='17';this.root.dataset.rigHead=p.head.toFixed(3);this.root.dataset.rigLeft=this.joints.left?.shoulder.toFixed(3);this.root.dataset.rigRight=this.joints.right?.shoulder.toFixed(3);
   if(window.pywebview?.api&&now-this.lastMask>150){this.lastMask=now;this.sendHitMask();}
  }
  sendHitMask(){
   if(!this.maskCanvas){this.maskCanvas=document.createElement('canvas');this.maskCanvas.width=60;this.maskCanvas.height=120;this.maskContext=this.maskCanvas.getContext('2d',{willReadFrequently:true});}
   const m=this.maskContext;m.clearRect(0,0,60,120);m.drawImage(this.canvas,0,0,60,120);const data=m.getImageData(0,0,60,120).data,rows=[];
   // Erode twelve logical pixels so the native hit surface stays under artwork
   // as bones ease between frames. Do not add a rectangular invisible blocker.
   const solid=(x,y)=>{for(const dx of [-3,0,3])for(const dy of [-3,0,3])if(data[((y+dy)*60+x+dx)*4+3]<220)return false;return true;};
   const box=this.canvas.getBoundingClientRect(),stage=this.root.querySelector('.character-stage');
   if(!stage||box.width<=0)return;
   for(let y=3;y<117;y+=2){let run=null;for(let x=3;x<57;x++){const on=solid(x,y);if(on&&run===null)run=x;if((!on||x===56)&&run!==null){if(x-run>=2)rows.push([box.x+run/60*box.width,box.y+y/120*box.height,(x-run)/60*box.width,2/120*box.height]);run=null;}}}
   this.root.dataset.hitRows=String(rows.length);window.pywebview.api.hitmask(rows,[window.innerWidth,window.innerHeight]).catch(error=>{this.root.dataset.hitError=String(error);});
  }
  dispose(){this.disposed=true;cancelAnimationFrame(this.raf);this.image.onload=null;this.canvas.remove();}
 }
 window.AltairRig={Rig,solveArm,zoneAt,poseAt,names};
})();
