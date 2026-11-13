const assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
async function fixture(deferred=false){
 let stopped=0,closed=0,resolveMedia,notifyMedia;const requested=new Promise(r=>notifyMedia=r);
 const stream={getTracks:()=>[{stop(){stopped++;}}]};
 const node=()=>({connect(){},disconnect(){}});
 class Context {constructor(){this.sampleRate=48000;this.audioWorklet={addModule:()=>Promise.resolve()};this.destination={};}createMediaStreamSource(){return node();}createGain(){return {...node(),gain:{value:1}};}resume(){return Promise.resolve();}close(){closed++;return Promise.resolve();}}
 const context={window:{addEventListener(){}},document:{addEventListener(){},hidden:false},navigator:{mediaDevices:{getUserMedia:()=>{notifyMedia();return deferred?new Promise(r=>resolveMedia=r):Promise.resolve(stream);}}},AudioContext:Context,AudioWorkletNode:class{constructor(){Object.assign(this,node());this.port={onmessage:null}}},fetch:async()=>({json:async()=>({installed:true})}),setTimeout:()=>1,clearTimeout(){},Float32Array,Int16Array,Uint8Array};
 vm.runInNewContext(fs.readFileSync('altair_core/web/listen.js','utf8'),context);
 const character={stopSpeech:async()=>{},unlockAudio:async()=>{},bubble:{textContent:''},caption:{textContent:''},root:{dataset:{}},set(){}};
 const listener=new context.window.AltairListener(character);
 return {listener,counts:()=>({stopped,closed}),requested,resolve:()=>resolveMedia(stream)};
}
(async()=>{
 let f=await fixture();await f.listener.start();assert.equal(f.listener.phase,'recording');await f.listener.cancel();assert.equal(f.counts().stopped,1);assert.equal(f.counts().closed,1);assert.equal(f.listener.phase,'idle');assert.equal(f.listener.chunks.length,0);console.log('PASS microphone tracks and audio context close on cancel');
 f=await fixture(true);const pending=f.listener.start();await f.requested;await f.listener.cancel();f.resolve();await pending;assert.equal(f.counts().stopped,1);assert.equal(f.listener.phase,'idle');console.log('PASS late microphone permission cannot reopen a cancelled capture');
 f=await fixture();await f.listener.start();await f.listener.finish();assert.equal(f.counts().stopped,1);assert.equal(f.counts().closed,1);assert.equal(f.listener.phase,'idle');console.log('PASS short capture releases microphone without starting recognition');
})().catch(e=>{console.error(e);process.exitCode=1});
