(()=>{
 if(window.__ligterVoiceController?.version===7)return;
 window.__ligterVoiceController?.destroy();
 const clips=new Map(),spoken=new Set();
 const rangeCalls=new Map();let selectedKey='',prepared=false,progress=null,waitFull=false,viewing=false;
 let enabled=false,dead=false,job=null,current=null,identityKey='',sequence=0,epoch=0,anchor=0;
 let lines=[],caption=null,critical='',showCaptions=true,bilingual=true,speak=true;
 let tailClock=null,processed=false,lastEnded=false;
 let watching,ticking,polling,retrying,pollBusy=false,tickBusy=false,lastTick=0,duck=null,lastPosition=0,pending=0,detach=()=>{};
 const host=document.createElement('div');host.id='ligter-voice-overlay-v7';
 host.style.cssText='position:absolute;bottom:11%;left:8%;width:84%;z-index:2147483646;pointer-events:none;text-align:center';
 const shadow=host.attachShadow({mode:'closed'});
 shadow.innerHTML='<style>.box{display:inline-block;max-width:980px;padding:9px 15px;border-radius:7px;background:#10181de8;color:#fff;font:600 clamp(17px,2.1vw,25px)/1.45 system-ui;white-space:pre-line;text-shadow:0 1px 2px #000}.source{font-size:.7em;font-weight:400;color:#d0d9db}.status{font-size:12px;font-weight:400;color:#c8eee2;margin-bottom:3px}.hidden{display:none}.loading{display:block;max-width:340px;margin:0 auto 8px;padding:9px 12px;background:#10181deb;color:#e7f4ef;border-radius:7px;text-align:left;font:12px/1.5 system-ui}.loading progress{display:block;width:100%;height:6px;margin:6px 0;accent-color:#62cab1}.loading .step{font-weight:600}.loading.hidden{display:none}</style><div class="loading hidden"><div class="step"></div><progress max="100" value="0" aria-label="Tiến độ xử lý audio"></progress><div class="detail"></div></div><div class="box hidden"><div class="status"></div><div class="source"></div><div class="target"></div></div>';
 const box=shadow.querySelector('.box'),status=shadow.querySelector('.status'),source=shadow.querySelector('.source'),target=shadow.querySelector('.target');
 const loading=shadow.querySelector('.loading'),step=shadow.querySelector('.step'),meter=shadow.querySelector('progress'),detail=shadow.querySelector('.detail');
 function restore(){if(duck){if(Math.abs(duck.video.volume-duck.applied)<.001)duck.video.volume=duck.original;duck=null}}
 async function send(type,data={}){
  try{
   if(!chrome.runtime?.id)throw Error('Extension context invalidated');
   const r=await chrome.runtime.sendMessage({target:'background',type,...data});
   if(r?.error)throw Error(r.error);return r||{};
  }catch(error){if(/context invalidated/i.test(error.message))destroy();throw error}
 }
 function video(){
  const visible=v=>{const r=v.getBoundingClientRect(),s=getComputedStyle(v);return v.isConnected&&r.height>50&&r.bottom>0&&r.top<innerHeight&&r.right>0&&r.left<innerWidth&&s.display!=='none'&&s.visibility!=='hidden'};
  const active=document.querySelector('[data-e2e="feed-active-video"] video');if(active&&visible(active))return active;
  const area=v=>{const r=v.getBoundingClientRect();return Math.max(0,Math.min(innerWidth,r.right)-Math.max(0,r.left))*Math.max(0,Math.min(innerHeight,r.bottom)-Math.max(0,r.top))};
  return [...document.querySelectorAll('video')].filter(visible).sort((a,b)=>area(b)-area(a))[0];
 }
 function identity(v){return v?.closest('[data-e2e-vid]')?.getAttribute('data-e2e-vid')||new URL(location.href).searchParams.get('modal_id')||location.pathname.match(/\/video\/(\d+)/)?.[1]||v?.currentSrc||location.href}
 function mount(){let frame=document.fullscreenElement||current?.parentElement?.closest('[data-xgplayerid]')||current?.parentElement||document.documentElement;
  if(frame.tagName==='VIDEO')frame=frame.parentElement;if(getComputedStyle(frame).position==='static')frame.style.position='relative';if(host.parentElement!==frame)frame.append(host);
 }
 function show(){
  const t=current?.currentTime||0,clock=lines.find(x=>x.start<=t+.02&&x.end>t),line=speak&&caption?caption:clock;
  loading.classList.toggle('hidden',!enabled||!job||!progress||prepared&&!current?.paused);
  if(progress){step.textContent=progress.done?'Đã chuẩn bị xong · Bấm phát video để xem':progress.label;if(progress.indeterminate)meter.removeAttribute('value');else meter.value=progress.percent??0;detail.textContent=progress.coverage_text+(progress.speech?.enabled?` · Giọng ${progress.speech.ready}/${progress.speech.total} câu`:'')}
  status.textContent=critical;source.textContent=showCaptions&&bilingual?(line?.source||''):'';target.textContent=showCaptions?(line?.translation||''):'';
  box.classList.toggle('hidden',!critical&&(!showCaptions||!line));
 }
 function metadata(e){if(e.source!==window||e.data?.type!=='LIGTER_MEDIA'||!Array.isArray(e.data.clips))return;
  for(const item of e.data.clips)if(/^\d{15,22}$/.test(item?.id)&&Array.isArray(item.sources)){clips.set(item.id,item);if(clips.size>150)clips.delete(clips.keys().next().value)}
 }
 window.addEventListener('message',metadata);
 function rangeResult(e){if(e.source!==window||e.data?.type!=='LIGTER_RANGE_RESULT')return;const call=rangeCalls.get(e.data.id);if(!call)return;rangeCalls.delete(e.data.id);clearTimeout(call.timer);call.resolve(e.data)}
 window.addEventListener('message',rangeResult);
 function fetchRange(m){return new Promise(resolve=>{const timer=setTimeout(()=>{rangeCalls.delete(m.id);resolve({id:m.id,error:'Hết thời gian đọc audio qua trình duyệt.'})},10000);rangeCalls.set(m.id,{resolve,timer});window.postMessage({type:'LIGTER_RANGE_REQUEST',id:m.id,url:m.url,range:m.range},location.origin)})}
 function retry(token){clearTimeout(retrying);retrying=setTimeout(()=>{if(enabled&&token===sequence)begin()},2500)}
 function undelivered(){return lines.some(x=>x.end>anchor-.05&&!spoken.has(x.id))}
 function resetSpeech(position){epoch++;anchor=position;spoken.clear();caption=null;tailClock=null;restore()}
 function position(){return tailClock??current.currentTime}
 async function begin(){
  if(!enabled||dead)return;
  const previousJob=job;const token=++sequence;clearTimeout(polling);clearTimeout(retrying);detach();restore();job=null;lines=[];caption=null;spoken.clear();epoch=0;pending=0;tailClock=null;processed=false;lastEnded=false;tickBusy=false;pollBusy=false;prepared=false;progress=null;viewing=false;
  const clearing=previousJob?send('timeline-stop',{job:previousJob}).catch(()=>{}):Promise.resolve();
  current=video();if(!current){critical='Chưa tìm thấy video. Đang chờ…';mount();show();retry(token);return}
  identityKey=identity(current);if(selectedKey&&identityKey!==selectedKey){await send('video-changed').catch(()=>{});await stop();return}if(!selectedKey){selectedKey=identityKey;if(!current.paused)current.pause()}anchor=0;lastPosition=current.currentTime;critical='Đang chuẩn bị lời dịch cho video này…';mount();show();
  const v=current;
  const ended=()=>{lastEnded=true};
  const seeking=()=>{const loop=(lastEnded||v.loop&&lastPosition>v.duration-1.5)&&v.currentTime<1;lastEnded=false;
   // A native loop must not move the unfinished narration/recognition clock
   // back to zero. Drain the first pass while the source keeps playing.
   if(loop&&speak&&(tailClock!==null||pending>0||!processed||undelivered())){tailClock=v.duration;return}
   resetSpeech(v.currentTime)};
  v.addEventListener('seeking',seeking);v.addEventListener('ended',ended);
  detach=()=>{v.removeEventListener('seeking',seeking);v.removeEventListener('ended',ended)};
  await clearing;if(token!==sequence||!enabled)return;
  let info=clips.get(identityKey);
  for(let n=0;!info&&n<28;n++){
   window.postMessage({type:'LIGTER_REQUEST_MEDIA',id:identityKey},location.origin);await new Promise(r=>setTimeout(r,120));
   if(token!==sequence||!enabled)return;info=clips.get(identityKey);
  }
  if(info&&!info.caption_urls?.length){
   window.postMessage({type:'LIGTER_REQUEST_MEDIA',id:identityKey},location.origin);
   await new Promise(r=>setTimeout(r,120));if(token!==sequence||!enabled)return;
   info=clips.get(identityKey)||info;
  }
  const usable=t=>['captions','subtitles'].includes(t.kind)&&(!(t.language||t.srclang)||/^(zh|cmn|en)(-|_|$)/i.test(t.language||t.srclang));
  const track=[...(v.textTracks||[])].find(t=>usable(t)&&t.cues?.length);
  const rows=Array.from(track?.cues||[],c=>[c.startTime,c.endTime,c.getCueAsHTML?.().textContent||c.text]);
  const caption_cues=new TextEncoder().encode(JSON.stringify(rows)).length<3500?rows:[];
  const caption_urls=[...new Set([...(info?.caption_urls||[]),...[...v.querySelectorAll('track[src]')].filter(usable).map(t=>t.src)])]
   .filter(url=>url.startsWith('https://')&&url.length<3000).slice(0,2);
  if(!info&&(caption_cues.length||caption_urls.length))info={sources:[],duration:v.duration};
  if(!info){critical='Chưa lấy được audio video. Đang thử lại; video gốc vẫn phát.';show();retry(token);return}
  try{
   const r=await send('direct-start',{video_id:identityKey,sources:info.sources,caption_urls,caption_cues,title:info.title||document.title,duration:info.duration||v.duration,position:anchor,url:location.href});
   if(token!==sequence||!enabled)return;job=r.job;critical='Đang chuẩn bị lời dịch…';poll(token);
  }catch(error){if(token===sequence&&enabled){critical=error.message;restore();show();retry(token)}}
 }
 async function poll(token){
  if(!enabled||token!==sequence||!job||pollBusy)return;pollBusy=true;
  try{
   const r=await send('direct-poll',{job,position:position()});if(token!==sequence)return;
   progress=r.progress||null;prepared=(waitFull?progress?.ready:progress?.can_play)===true;lines=r.lines||[];showCaptions=r.subtitles!==false;bilingual=r.bilingual!==false;speak=r.speak!==false;
   let covered=anchor;for(const range of [...(r.coverage||[])].sort((a,b)=>a[0]-b[0]))if(range[0]<=covered+.1)covered=Math.max(covered,range[1]);
   processed=r.state==='ready'||Number.isFinite(current.duration)&&covered>=current.duration-.1;
   if(!speak&&tailClock!==null)resetSpeech(current.currentTime);
   if(r.state==='cancelled'||r.state==='error'){critical=r.error||'Đang nối lại dịch cho video hiện tại…';restore();show();if(!viewing)retry(token);return}
   critical=r.state==='error'?(r.error||r.message):!lines.length?(r.message||'Đang nhận diện lời nói…'):'';
  }catch(error){if(token===sequence&&enabled){restore();critical=error.message;
   if(/Phiên đã hết|Không tìm thấy phiên/i.test(error.message)){pollBusy=false;retry(token);show();return}
  }}finally{if(token===sequence)pollBusy=false}
  if(token===sequence&&enabled){show();polling=setTimeout(()=>poll(token),500)}
 }
 async function tick(){
  if(!enabled||!current||!job||(!prepared&&!viewing)||tickBusy||Date.now()-lastTick<180)return;
  if(prepared&&!current.paused)viewing=true;
  tickBusy=true;lastTick=Date.now();const token=sequence,v=current;
  if(tailClock!==null&&processed&&!pending&&!undelivered())resetSpeech(v.currentTime);
  const t=position();
  const next=lines.filter(x=>x.end>anchor-.05&&!spoken.has(x.id)&&x.start<t+45).slice(0,40);
  try{
   const r=await send('timeline',{job,position:t,anchor,ended:v.ended,paused:v.paused||v.seeking,user_paused:v.paused&&!v.ended,seeking:v.seeking,seek_epoch:epoch,rate:v.playbackRate,
    next:next.map(x=>({id:x.id,start:x.start,end:x.end,source:x.source,translation:x.translation}))});
   if(token!==sequence||current!==v)return;
   if(r.protocol!==7){critical='Cần tải lại tiện ích để nạp bộ phát mới.';restore();show();return}
   for(const id of r.completed_ids||[])spoken.add(id);pending=r.pending||0;caption=speak?(r.caption||null):null;
   if(r.error){critical=r.error;restore()}
   else if(r.speaking){critical='';if(!duck){duck={video:v,original:v.volume,applied:v.volume*.25};v.volume=duck.applied}}
   else restore();
   lastPosition=v.currentTime;show();
  }catch(error){if(token===sequence&&enabled){critical=error.message;restore();show()}}
  finally{if(token===sequence)tickBusy=false}
 }
 async function stop(){enabled=false;sequence++;clearInterval(watching);clearInterval(ticking);clearTimeout(polling);clearTimeout(retrying);detach();restore();job=null;caption=null;lines=[];critical='';selectedKey='';prepared=false;progress=null;viewing=false;host.remove();await send('timeline-stop').catch(()=>{})}
 function start(force=false,full=false){if(enabled&&!force)return Promise.resolve();if(dead)return Promise.reject(Error('Tải lại trang để bật dịch.'));enabled=true;selectedKey='';waitFull=full;
  clearInterval(watching);clearInterval(ticking);watching=setInterval(()=>{const v=video();if(current&&(!v||v!==current||!current.isConnected||identity(v)!==selectedKey)){send('video-changed').catch(()=>{});stop()}},200);ticking=setInterval(tick,100);return begin();
 }
 function message(m,s,reply){if(s.id!==chrome.runtime.id)return;
  if(m.type==='ligter-play-prepared'){if(!prepared||!current){reply({error:'Video chưa chuẩn bị xong.'});return}viewing=true;resetSpeech(0);current.currentTime=0;current.play().then(()=>reply({ok:true})).catch(e=>reply({error:e.message}));return true}
  if(m.type==='ligter-media-fetch'){fetchRange(m).then(reply);return true}
  if(m.type==='ligter-v7-direct'){start(!!m.force,m.wait_full===true).then(()=>reply({ok:true})).catch(e=>reply({error:e.message}));return true}
  if(['ligter-clear','ligter-v6-clear','ligter-v7-clear'].includes(m.type)){stop().then(()=>reply({ok:true}));return true}
  // These controls run only after an explicit transcript-panel action.
  if(['ligter-v7-seek','ligter-v6-seek','ligter-seek'].includes(m.type)&&current){lastEnded=false;lastPosition=Math.max(0,Number(m.position)||0);current.currentTime=lastPosition;reply({ok:true});return}
  if(['ligter-v7-toggle','ligter-v6-toggle','ligter-toggle'].includes(m.type)&&current){if(current.paused)current.play().catch(()=>{});else current.pause();reply({ok:true});return}
  if(m.type==='ligter-capture-buffer'){critical=m.paused?'Dịch đang chậm hơn nguồn; video vẫn tiếp tục phát.':'';show();reply({ok:true});return}
  if(m.type==='ligter-line'){critical='';source.textContent=m.source||'';target.textContent=m.text||'';box.classList.remove('hidden');mount()}
 }
 chrome.runtime.onMessage.addListener(message);
 function remount(){if(enabled&&current)mount()}
 function destroy(){if(dead)return;dead=true;enabled=false;sequence++;clearInterval(watching);clearInterval(ticking);clearTimeout(polling);clearTimeout(retrying);detach();restore();host.remove();
  for(const [id,call] of rangeCalls){clearTimeout(call.timer);call.resolve({id,error:'Trang đã chuyển.'})}rangeCalls.clear();
  window.removeEventListener('message',rangeResult);window.removeEventListener('message',metadata);document.removeEventListener('fullscreenchange',remount);try{chrome.runtime.onMessage.removeListener(message)}catch{}window.removeEventListener('pagehide',destroy);
 }
 document.addEventListener('fullscreenchange',remount);window.addEventListener('pagehide',destroy);
 window.__ligterVoiceController={version:7,destroy};
 // Each video requires an explicit Start from the popup or transcript panel.
})();
