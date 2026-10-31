/* Narration follows the source player. It never asks the page to pause and
   its volume is independent of the source video's muted property. */
class LigterSpeechTimeline {
 constructor(load,create=audio=>new Audio('data:audio/mpeg;base64,'+audio)){
  this.load=load;this.create=create;this.serial=0;this.reset();
 }
 reset(){
  this.serial++;this.player?.pause();if(this.player)this.player.src='';
  this.player=null;this.active=null;this.job='';this.voice='';this.epoch=0;
  this.anchor=0;this.pending=new Map();this.completed=new Set();this.audio=new Map();
  this.loading=new Set();this.failures=new Map();this.last=null;this.problem='';this.enabled=null;this.blockedAt=-Infinity;
  this.message=null;this.speed=1.15;this.speedTime=performance.now();
 }
 prepare(line){
  if(this.audio.has(line.id)||this.loading.has(line.id)||this.loading.size>=2)return;
  const failure=this.failures.get(line.id);
  if(failure&&(failure.count>=3||Date.now()<failure.retry))return;
  const serial=this.serial;this.loading.add(line.id);
  const job=this.job,voice=this.voice;
  Promise.resolve().then(()=>this.load(job,line.id,voice)).then(result=>{
   if(serial!==this.serial)return;
   if(result?.error)throw Error(result.error);
   if(result?.audio){this.audio.set(line.id,result.audio);this.failures.delete(line.id);this.problem=''}
  }).catch(error=>{
   if(serial!==this.serial)return;
   const count=(this.failures.get(line.id)?.count||0)+1;
   this.failures.set(line.id,{count,retry:Date.now()+2500});this.problem=error.message;
  }).finally(()=>{if(serial===this.serial)this.loading.delete(line.id)});
 }
 start(line,m){
  const p=this.create(this.audio.get(line.id));this.player=p;this.active=line;
  p.preservesPitch=true;p.playbackRate=this.speed;p.muted=false;p.volume=this.volume(m);
  p.onloadedmetadata=()=>{if(this.player===p)this.adjust(this.message||m)};
  this.adjust(m);
  p.onended=()=>{if(this.player!==p)return;this.completed.add(line.id);this.pending.delete(line.id);
   this.player=null;this.active=null;this.problem='';
   // Chain ready dialogue on the audio event, without adding a polling gap
   // after every sentence. Keep the most recent native pause/seek state.
   if(this.message)this.advance(this.message)};
  p.onerror=()=>{if(this.player!==p)return;this.player=null;this.active=null;this.audio.delete(line.id);
   this.failures.set(line.id,{count:1,retry:Date.now()+1500});this.problem='Chưa phát được câu đọc. Đang thử lại…'};
  this.play(p);
 }
 play(p){
  if(performance.now()-this.blockedAt<1500)return;
  try{Promise.resolve(p.play()).catch(error=>{if(this.player===p){this.problem=error.name==='NotAllowedError'?'Chrome đang chặn phát giọng. Bấm phát video rồi thử lại.':error.message;this.blockedAt=performance.now()}})}
  catch(error){this.problem=error.message}
 }
 lag(m){
  const line=this.active||[...this.pending.values()].sort((a,b)=>a.start-b.start)[0];
  if(!line)return 0;
  const p=this.player,progress=p&&Number.isFinite(p.duration)&&p.duration>0?Math.min(1,p.currentTime/p.duration):0;
  return Math.max(0,m.position-line.start-(line.end-line.start)*progress);
 }
 adjust(m){
  const now=performance.now(),elapsed=Math.min(.5,Math.max(0,(now-this.speedTime)/1000));this.speedTime=now;
  const sourceRate=Math.min(2,Math.max(.5,Number(m.rate)||1)),base=Math.min(1.4,Math.max(1,1.15*sourceRate));
  let target=base+Math.max(0,this.lag(m)-1)*.06;
  const p=this.player;
  if(p&&Number.isFinite(p.duration)){
   // Two seconds of slack allows natural phrasing. Approaching an overrun
   // raises the rate before a queue of rapid replies can build up.
   const budget=Math.max(.5,(this.active.end+2-m.position)/sourceRate);
   target=Math.max(target,(p.duration-p.currentTime)/budget);
  }
  target=Math.min(1.4,Math.max(base,target));
  const step=elapsed*(target>this.speed ? .12 : .08);
  this.speed+=Math.max(-step,Math.min(step,target-this.speed));
  this.speed=Math.min(1.4,Math.max(base,this.speed));
  if(p)p.playbackRate=this.speed;
 }
 paused(m){return !!m.seeking||m.user_paused===true||!!m.paused&&!m.ended}
 advance(m){
  if(this.player||!m.config.speak||this.paused(m))return;
  const due=[...this.pending.values()].sort((a,b)=>a.start-b.start||a.end-b.end).find(line=>line.start<=m.position+.12);
  if(due&&this.audio.has(due.id))this.start(due,m);
 }
 tick(m){
  const epoch=m.seek_epoch||0;
  const changed=this.job!==m.job||this.voice!==m.config.voice||epoch!==this.epoch||this.enabled!==!!m.config.speak;
  const jumped=this.last&&!changed&&m.position<this.last.position-.8;
  if(changed||jumped&&!this.pending.size){const newContext=this.job!==m.job||epoch!==this.epoch;this.reset();this.job=m.job;this.voice=m.config.voice;this.epoch=epoch;this.enabled=!!m.config.speak;this.anchor=newContext&&Number.isFinite(m.anchor)?m.anchor:m.position}
  this.last={position:m.position};this.message=m;
  if(!m.config.speak){this.player?.pause();return {protocol:7,speaking:false,hold:false,caption:null,pending:0}}
  for(const line of m.next||[]){
   if(!line?.id||!Number.isFinite(line.start)||!Number.isFinite(line.end)||line.end<=line.start)continue;
   if(line.end<this.anchor-.05||this.completed.has(line.id))continue;
   this.pending.set(line.id,line);
  }
  const ordered=[...this.pending.values()].sort((a,b)=>a.start-b.start||a.end-b.end);
  for(const line of ordered.slice(0,8))this.prepare(line);
  if(this.paused(m)){this.player?.pause();this.speedTime=performance.now();return this.state(m)}
  this.adjust(m);
  if(this.player){this.player.muted=false;this.player.volume=this.volume(m);if(this.player.paused&&!this.player.ended)this.play(this.player)}
  this.advance(m);
  // Discard only completed cache entries, never waiting speech.
  if(this.audio.size>100)for(const id of this.audio.keys()){
   if(this.completed.has(id))this.audio.delete(id);if(this.audio.size<=80)break;
  }
  return this.state(m);
 }
 state(m){
  const due=[...this.pending.values()].filter(x=>!this.completed.has(x.id)&&x.start<=m.position+.12).sort((a,b)=>a.start-b.start)[0];
  const waiting=!!due&&!this.player;
  const speaking=!!this.player&&!this.player.paused&&!this.player.ended&&this.player.readyState>=2&&this.player.currentTime>0&&this.player.volume>0&&!this.player.muted;
  return {protocol:7,speaking,
   hold:false,waiting,line_id:this.active?.id||due?.id||'',caption:this.active||due||null,
   audio_time:this.player?.currentTime||0,audio_volume:this.player?.volume||0,audio_muted:!!this.player?.muted,
   remaining:this.player&&Number.isFinite(this.player.duration)?Math.max(0,this.player.duration-this.player.currentTime):null,
   rate:this.speed,lag:this.lag(m),error:this.problem,completed:this.completed.size,completed_ids:[...this.completed].slice(-4),pending:this.pending.size};
 }
 volume(m){const value=Number(m.config.narration_volume??1);return Number.isFinite(value)?Math.min(1,Math.max(0,value)):1}
}
