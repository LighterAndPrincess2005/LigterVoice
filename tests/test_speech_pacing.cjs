const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const flush=()=>new Promise(resolve=>setImmediate(resolve));

// A media clock advances independently from the timeline tick. This catches
// idle polling time accumulating after hundreds of short spoken replies.
async function simulate(code,{count=240,spacing=.6,load=1.28,nativeEOF=true,startDelay=0}={}){
 let now=0,created=0,interrupted=0;
 const context=vm.createContext({performance:{now:()=>now},Date,console});vm.runInContext(code,context);
 const Timeline=vm.runInContext('LigterSpeechTimeline',context);
 class Audio{
  constructor(){this.duration=spacing*load;this.currentTime=0;this.paused=true;this.ended=false;this.readyState=4;this.volume=1;this.muted=false;created++}
  play(){this.paused=false;return Promise.resolve()}
  pause(){if(!this.paused&&this.currentTime<this.duration)interrupted++;this.paused=true}
  finish(){this.currentTime=this.duration;this.ended=true;this.paused=true;this.onended?.()}
 }
 const timeline=new Timeline(async(job,id)=>({audio:id}),()=>new Audio());
 const lines=Array.from({length:count},(_,i)=>({id:'s'+i,start:i*spacing,end:(i+1)*spacing})),duration=count*spacing;
 let elapsed=0,frame=0,maxLag=0,maxRateStep=0,lastRate=null,peakRate=0;
 while(elapsed<duration*3&&timeline.completed.size<count){
  now=elapsed*1000;
  if(frame%10===0){
   const ended=elapsed>=duration;
   const report=timeline.tick({job:'continuous-film',anchor:0,position:Math.min(duration,elapsed),rate:1,ended,user_paused:false,
    config:{voice:'female',speak:true},paused:ended&&nativeEOF,
    next:elapsed<startDelay?[]:lines.filter(x=>!timeline.completed.has(x.id)&&x.start<Math.min(duration,elapsed)+45).slice(0,40)});
   assert.equal(report.hold,false);await flush();
   if(elapsed>2&&elapsed<duration)maxLag=Math.max(maxLag,report.lag||0);
  }
  let remaining=.02,guard=0;
  while(remaining>1e-7&&timeline.player&&!timeline.player.paused&&guard++<10){
   const p=timeline.player,rate=p.playbackRate;
   assert.equal(p.preservesPitch,true);
   if(lastRate!==null)maxRateStep=Math.max(maxRateStep,Math.abs(rate-lastRate));lastRate=rate;peakRate=Math.max(peakRate,rate);
   const wall=(p.duration-p.currentTime)/rate;
   if(wall<=remaining+1e-9){remaining-=wall;p.finish()}else{p.currentTime+=remaining*rate;remaining=0}
  }
  elapsed+=.02;frame++;
 }
 return {source_seconds:duration,wall_seconds:+elapsed.toFixed(2),tail_seconds:+Math.max(0,elapsed-duration).toFixed(2),
  completed:timeline.completed.size,created,interrupted,max_lag_seconds:+maxLag.toFixed(2),peak_rate:+peakRate.toFixed(3),max_rate_step:+maxRateStep.toFixed(4)};
}

module.exports={simulate};
if(require.main===module)(async()=>{
 const code=fs.readFileSync('extension/speech-timeline.js','utf8');
 const steady=await simulate(code),rapid=await simulate(code,{count:400,spacing:.3,load:1.12});
 for(const result of [steady,rapid]){
  assert.equal(result.completed,result.created,'each sentence is spoken once');assert.equal(result.interrupted,0,'no spoken sentence is cut');
  assert(result.tail_seconds<5,JSON.stringify(result));assert(result.peak_rate<=1.4);assert(result.max_rate_step<=.025);
 }
 const overloaded=await simulate(code,{count:80,spacing:.6,load:1.8});
 assert.equal(overloaded.completed,80,'even speech beyond the rate cap is retained to the end');assert(overloaded.peak_rate<=1.4);assert.equal(overloaded.interrupted,0);
 const long=await simulate(code,{count:1000,spacing:.6,load:1.28}),cold=await simulate(code,{count:240,spacing:.6,load:1.28,startDelay:12});
 assert.equal(long.completed,1000);assert(long.tail_seconds<5,'backlog must not grow with video length');
 assert.equal(cold.completed,240);assert(cold.tail_seconds<6,'bounded catch-up should recover an initial preparation delay');
 console.log('PASS independent media-clock simulation:',JSON.stringify({steady,rapid,overloaded,long,cold}));
})().catch(error=>{console.error(error);process.exitCode=1});
