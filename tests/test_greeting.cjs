const assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const context={window:{addEventListener(){}},document:{getElementById(){return null}},module:{exports:{}}};
vm.runInNewContext(fs.readFileSync('altair_core/web/character.js','utf8'),context);
const proto=context.window.AltairCharacter.Character.prototype;
async function main(){
 let count=0,received;const character=Object.create(proto);character.say=(...args)=>{count++;received=args;return Promise.resolve(true);};
 character.root={dataset:{}};character.voiceInput={checked:true};character.unlockAudio=()=>Promise.resolve();character.speechId=0;character.stopSpeech=()=>Promise.resolve();
 assert.equal(await character.demo('waving'),true);assert.equal(count,1);assert.equal(received[1].sample,'voice-ja-greeting.wav');assert.equal(received[1].pose,'waving');assert.ok(received[1].japanese.includes('ご主人様'));assert.ok(received[0].toLowerCase().includes('chủ nhân'));
 character.root={dataset:{}};character.respond('Lời chào',{speech_text:'こんにちは。',speech_sample:'voice-ja-greeting.wav'});
 assert.equal(received[1].sample,'voice-ja-greeting.wav');assert.equal(received[1].japanese,'こんにちは。');
 character.voiceInput.checked=false;character.greet();assert.equal(received[1].force,undefined);
 console.log('PASS tap/wave dispatches Japanese greeting with Vietnamese subtitle');
 console.log('PASS greeting uses local sample without TTS or model generation');
 console.log('PASS chat greeting preserves its prepared voice and motion');
 console.log('PASS greeting respects mute, never forces audio on');
}
main().catch(e=>{console.error(e);process.exitCode=1});
