const assert=require('node:assert/strict');const {cameraClamp,mouthLevel,definitions}=require(require('node:path').resolve('altair_core/web/character.js'));let passed=0;
function check(name,fn){fn();passed++;console.log('PASS',name);}
check('camera cannot drag above head or below boots',()=>{assert.equal(cameraClamp(100,800,400,1),0);assert.equal(cameraClamp(-999,800,400,1),-400);assert.equal(cameraClamp(-170,800,400,1),-170);});
check('fit-to-body has no invisible pan region',()=>{assert.equal(cameraClamp(-100,800,400,.5),0);assert.equal(cameraClamp(100,800,400,.5),0);});
check('zoom clamps correctly at small and large scale',()=>{assert.equal(cameraClamp(-10000,800,400,1.8),-1040);assert.equal(cameraClamp(-20,800,400,.4),0);});
check('silent audio closes lips rapidly',()=>{let previous=1;for(let i=0;i<8;i++)previous=mouthLevel(new Float32Array(512),previous).level;assert.ok(previous<.002);});
check('real waveform opens lips, with smoothed amplitude',()=>{const wave=Float32Array.from({length:512},(_,i)=>Math.sin(i/7)*.14);const r=mouthLevel(wave,0);assert.ok(r.rms>.09);assert.ok(r.level>.2&&r.level<1);});
check('empty and low-noise input never fabricates speech',()=>{assert.equal(mouthLevel([],0).level,0);assert.equal(mouthLevel(new Float32Array(512).fill(.001),0).level,0);});
check('fallback camera metadata remains valid across rig states',()=>{assert.ok(Object.keys(definitions).length>=28);for(const state of Object.values(definitions)){assert.ok(state.bust.length);assert.ok(state.body.length);assert.ok(state.bust.every(x=>x>=0&&x<16));assert.ok(state.body.every(x=>x>=0&&x<8));}});
console.log(JSON.stringify({passed,failed:0}));
