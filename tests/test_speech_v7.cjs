const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
let now=0;const context=vm.createContext({performance:{now:()=>now},Date,console});
vm.runInContext(fs.readFileSync('extension/speech-timeline.js','utf8'),context);const Timeline=vm.runInContext('LigterSpeechTimeline',context);
class Audio{constructor(id,duration){this.id=id;this.duration=duration;this.currentTime=0;this.paused=true;this.ended=false;this.readyState=4;this.volume=1;this.muted=false}play(){this.paused=false;return Promise.resolve()}pause(){this.paused=true}finish(){this.currentTime=this.duration;this.ended=true;this.paused=true;this.onended?.()}}
const flush=()=>new Promise(r=>setImmediate(r));
(async()=>{
 const created=[],timeline=new Timeline(async(job,id)=>({audio:id}),id=>{const a=new Audio(id,{a:3,b:.7,c:1.5,d:2}[id]);created.push(a);return a});
 const lines=[{id:'a',start:0,end:1,translation:'Một câu dài.'},{id:'b',start:1,end:1.3,translation:'Vâng.'},{id:'c',start:1.31,end:2.2,translation:'Một câu khác.'}];
 let state={job:'video-1',position:0,anchor:0,paused:false,user_paused:false,muted:true,rate:1,seek_epoch:0,config:{voice:'male',speak:true,playback_mode:'complete'},next:lines};
 const tick=(position,extra={})=>{now+=200;state={...state,position,...extra};const r=timeline.tick(state);assert.equal(r.hold,false,'no config or missing audio may request a source-video hold');return r};
 tick(0);await flush();tick(0);const first=timeline.player;assert.equal(first.id,'a');assert.equal(first.volume,1,'muting Chinese video must not silence Vietnamese narration');assert.equal(first.muted,false);
 first.currentTime=.7;let report=tick(1.4);assert.equal(timeline.player,first,'new dialogue cannot cut the current voice');assert.equal(report.speaking,true);assert.equal(report.protocol,7);assert.equal(report.audio_volume,1);
 tick(1.4,{paused:true,user_paused:true});assert.equal(first.paused,true);tick(1.4,{paused:false,user_paused:false});assert.equal(first.paused,false);assert.equal(timeline.player,first);
 first.finish();tick(12);assert.equal(timeline.player.id,'b','elapsed rapid replies remain queued');timeline.player.finish();tick(12);await flush();tick(12);assert.equal(timeline.player.id,'c');timeline.player.finish();tick(12);assert.equal(timeline.completed.size,3);
 tick(50,{seek_epoch:1,next:[{id:'d',start:50,end:52}]});await flush();tick(50);assert.equal(timeline.player.id,'d');assert(timeline.player.playbackRate>=1.15&&timeline.player.playbackRate<=1.4);assert.equal(timeline.player.preservesPitch,true);
 const old=timeline.player;tick(51,{config:{voice:'male',speak:false}});assert.equal(old.paused,true);assert.equal(timeline.player,null,'voice-off releases old playback');
 tick(60,{config:{voice:'female',speak:true},next:[]});assert.equal(timeline.pending.size,0);
 const delayed=new Timeline(async(job,id)=>({audio:id}),id=>new Audio(id,2));const m={...state,job:'delayed',position:20,anchor:0,config:{voice:'female',speak:true},next:lines};delayed.tick(m);await flush();delayed.tick(m);assert.equal(delayed.player.id,'a','delayed preparation retains original anchor');
 const tail=new Timeline(async(job,id)=>({audio:id}),id=>new Audio(id,1));
 const eof={...m,job:'eof',position:2.2,ended:true,paused:true,user_paused:false};tail.tick(eof);await flush();tail.tick(eof);assert.equal(tail.player.id,'a','native EOF must not pause the unfinished voice');
 tail.player.finish();assert.equal(tail.player.id,'b','ready replies chain immediately on audio end, without waiting for a page tick');
 tail.tick({...eof,user_paused:true});assert.equal(tail.player.paused,true,'explicit user pause still wins at EOF');
 tail.tick(eof);assert.equal(tail.player.paused,false);tail.player.finish();tail.tick(eof);await flush();tail.tick(eof);assert.equal(tail.player.id,'c');tail.player.finish();assert.equal(tail.completed.size,3);assert.equal(tail.player,null);
 // Continuous playback and backward seeking must not replay completed IDs.
 const seen=[],longTimeline=new Timeline(async(job,id)=>({audio:id}),id=>{seen.push(id);return new Audio(id,.12)});
 const many=Array.from({length:90},(_,i)=>({id:'regression-'+i,start:490+i*.2,end:490+i*.2+.18,source:'source '+i,translation:'Câu dịch '+i}));
 const runMessage={...state,job:'continuous-regression',position:490,anchor:490,seek_epoch:0,config:{voice:'female',speak:true},next:many};
 for(let frame=0;frame<300;frame++){
  now+=100;runMessage.position=490+frame*.1;longTimeline.tick(runMessage);await flush();
  if(longTimeline.player){longTimeline.player.currentTime+=.1*longTimeline.player.playbackRate;if(longTimeline.player.currentTime>=longTimeline.player.duration)longTimeline.player.finish()}
 }
 assert.equal(seen.length,90);assert.equal(new Set(seen).size,90,'watching straight through never replays a completed line');
 const beforeSeek=seen.length;runMessage.seek_epoch=1;runMessage.anchor=500;runMessage.position=500;runMessage.next=many.filter(x=>x.end>500);
 for(let frame=0;frame<180;frame++){
  now+=100;runMessage.position=500+frame*.1;longTimeline.tick(runMessage);await flush();
  if(longTimeline.player){longTimeline.player.currentTime+=.1*longTimeline.player.playbackRate;if(longTimeline.player.currentTime>=longTimeline.player.duration)longTimeline.player.finish()}
 }
 assert.equal(seen.length-beforeSeek,40,'backward seek rebuilds only the selected interval');
 assert.equal(new Set(seen.slice(beforeSeek)).size,40,'each line after seek also plays only once');
 console.log('PASS independent narration volume, no source holds, full tails, immediate sentence chaining, native pause/resume, EOF drain, seek, voice off, pitch preservation and bounded speed');
})().catch(e=>{console.error(e);process.exitCode=1});
