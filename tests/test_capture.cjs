const assert=require('node:assert/strict');
const fs=require('node:fs');const vm=require('node:vm');
(async()=>{
 const sent=[],pending=[];
 const context=vm.createContext({console,performance,Audio:class{},Float32Array,Uint8Array,DataView,ArrayBuffer,
  btoa:s=>Buffer.from(s,'binary').toString('base64'),atob:s=>Buffer.from(s,'base64').toString('binary'),
  chrome:{runtime:{onMessage:{addListener(){}},sendMessage:m=>{sent.push(m);return new Promise(resolve=>pending.push(resolve))}}}});
 vm.runInContext(fs.readFileSync('extension/speech-timeline.js','utf8'),context);
 vm.runInContext(fs.readFileSync('extension/offscreen-v7.js','utf8'),context);
 vm.runInContext('tabId=42',context);
 const frame=(loud,n=1)=>{for(let i=0;i<n;i++)context.captureFrame(new Float32Array(1600).fill(loud ? 0.1 : 0),16000,0)};
 frame(true,4);frame(false,3);assert.equal(sent.length,0,'short hesitation must not cut the utterance');
 frame(true,2);frame(false,5);assert.equal(sent.filter(x=>x.type==='audio').length,1);
 const wav=Buffer.from(sent[0].audio,'base64');assert.equal(wav.toString('ascii',0,4),'RIFF');
 assert.ok(wav.length<16000*2*4,'natural endpoint should not wait for a four-second block');
 frame(true,4);frame(false,5);frame(true,4);frame(false,5);
 assert.equal(vm.runInContext('captureQueue.length',context),2,'speech recorded while the service is busy must be queued');
 pending.shift()({});await new Promise(r=>setImmediate(r));
 assert.equal(sent.filter(x=>x.type==='audio').length,2,'queued utterance must be sent after the first completes');
 console.log('PASS natural speech endpoint, hesitation continuity, valid WAV, no busy-utterance loss');
})().catch(e=>{console.error(e);process.exit(1)});
