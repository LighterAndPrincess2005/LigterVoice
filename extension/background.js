const BASE='http://127.0.0.1:38479';let cfgCache=null,cfgTime=0,lastReport=0,creatingOffscreen=null;
async function api(path,body={},binary=false){const {token}=await chrome.storage.local.get('token');if(!token)throw Error('Dán mã kết nối từ app trước.');let r;try{r=await fetch(BASE+path,{method:'POST',headers:{Authorization:'Bearer '+token,'Content-Type':binary?'application/octet-stream':'application/json'},body:binary?body:JSON.stringify(body),signal:AbortSignal.timeout(path==='/jobs/start'?12000:path==='/speech'?15000:5000)})}catch{throw Error('Không kết nối được app. Kiểm tra Ligter Voice đang mở.')}const result=await r.json();if(!r.ok)throw Error(result.error||'App trả lỗi.');return result}
const getActive=async()=>(await chrome.storage.session.get('active')).active;
const generations=new Map(),starts=new Map();let mediaPulling=false;
function invalidate(tab){const n=(generations.get(tab)||0)+1;generations.set(tab,n);return n}
function serialStart(tab,fn){const p=(starts.get(tab)||Promise.resolve()).catch(()=>{}).then(fn);starts.set(tab,p);const clean=()=>{if(starts.get(tab)===p)starts.delete(tab)};p.then(clean,clean);return p}
async function pumpMedia(tabId){if(mediaPulling)return;mediaPulling=true;try{const r=await api('/media/pull',{owner:'tab-'+tabId});for(const request of r.requests||[]){chrome.tabs.sendMessage(tabId,{type:'ligter-media-fetch',...request}).then(result=>api('/media/push',{...result,id:request.id})).catch(error=>api('/media/push',{id:request.id,error:error.message}).catch(()=>{}))}}catch{}finally{mediaPulling=false}}
async function offscreen(){if(await chrome.offscreen.hasDocument())return;if(!creatingOffscreen)creatingOffscreen=chrome.offscreen.createDocument({url:'offscreen.html',reasons:['USER_MEDIA','AUDIO_PLAYBACK'],justification:'Phát thuyết minh đồng bộ video và thu âm tab khi người dùng chọn.'}).finally(()=>{creatingOffscreen=null});await creatingOffscreen}
async function audioTimeline(message){await offscreen();try{return await chrome.runtime.sendMessage(message)}catch(error){if(!/receiving end|connection|closed/i.test(error.message))throw error;await offscreen();await new Promise(resolve=>setTimeout(resolve,100));return await chrome.runtime.sendMessage(message)}}
async function stop(){const active=await getActive();const {warm}=await chrome.storage.session.get('warm');if(active)invalidate(active.tabId);await chrome.storage.session.remove(['active','snapshot','snapshot_at','warm']);if(active?.tabId!==undefined)await chrome.tabs.sendMessage(active.tabId,{type:'ligter-clear'}).catch(()=>{});if(await chrome.offscreen.hasDocument())await chrome.runtime.sendMessage({target:'offscreen',type:'stop'}).catch(()=>{});for(const job of [active?.job,warm?.job])if(job)api('/jobs/cancel',{job}).catch(()=>{});await chrome.storage.local.set({status:'Đã dừng dịch.'})}
async function settings(){const r=await api('/status');if(!r.ready)throw Error('Nhập khóa dịch vụ AI trong app trước.');if(!r.version||r.version.localeCompare('0.8.3',undefined,{numeric:true})<0)throw Error('Mở app Ligter Voice 0.8.3 để dùng chế độ xem sớm.');cfgCache=r;cfgTime=Date.now();return r}
chrome.runtime.onMessage.addListener((m,s,respond)=>{if(s.id!==chrome.runtime.id||m.target!=='background')return;const popup=s.url===chrome.runtime.getURL('popup.html');const panel=s.url===chrome.runtime.getURL('panel.html');const audio=s.url===chrome.runtime.getURL('offscreen.html');(async()=>{
 if((popup||panel)&&m.type==='connect'){const r=await api('/status');const active=await getActive();const enabled=!!active&&active.enabled!==false;return {...r,enabled,message:enabled?'Đang xử lý video đã chọn.':r.ready?'Đã kết nối. Chọn video rồi bấm dịch.':'Đã kết nối; hãy nhập khóa dịch vụ AI trong app.'}}
 if((popup||panel)&&m.type==='start'){
  const [tab]=await chrome.tabs.query({active:true,currentWindow:true});if(!/^https?:/.test(tab?.url||''))throw Error('Mở trang video trước.');await settings();await stop();await chrome.scripting.executeScript({target:{tabId:tab.id},files:['content-v7.js']});await offscreen();
  await chrome.storage.session.set({active:{tabId:tab.id,mode:'direct',enabled:true,voice:cfgCache.voice,speak:cfgCache.speak,wait_full:m.wait_full===true}});
  chrome.tabs.sendMessage(tab.id,{type:'ligter-v7-direct',force:true,wait_full:m.wait_full===true}).catch(e=>chrome.storage.local.set({status:e.message}));await chrome.storage.local.set({status:'Đang đệm video đã chọn.'});return {enabled:true,message:'Đang chuẩn bị phần đầu. Đủ chữ và giọng sẽ hiện Xem ngay.',player_version:7};
 }
 if((popup||panel)&&m.type==='stop'){await stop();return {enabled:false,message:'Đã dừng dịch.'}}
 const active=await getActive();const content=!!s.tab&&s.frameId===0&&s.tab.id===active?.tabId;
 if(content&&m.type==='resume')return {enabled:false};
 if(content&&m.type==='video-changed'){await stop();return {ok:true}}
 if(content&&m.type==='direct-start'){
  const tab=s.tab.id,seq=invalidate(tab);
  return await serialStart(tab,async()=>{
   let now=await getActive();if(generations.get(tab)!==seq||now?.tabId!==tab||now.enabled===false)return {superseded:true};
   if(now.video_id&&now.video_id!==m.video_id)throw Error('Video đã thay đổi. Bấm Dịch video này để bắt đầu.');
   const r=await api('/jobs/start',{...m,position:0,prepare_full:true,transport:'browser',owner:'tab-'+tab});
   now=await getActive();if(generations.get(tab)!==seq||now?.tabId!==tab||now.enabled===false){await api('/jobs/cancel',{job:r.job}).catch(()=>{});return {superseded:true}}
   await chrome.storage.session.remove(['snapshot','snapshot_at']);await chrome.storage.session.set({active:{...now,job:r.job,video_id:m.video_id}});return r;
  });
 }
 if(content&&m.type==='direct-poll'&&m.job===active.job){pumpMedia(s.tab.id);const r=await api('/jobs/poll',{job:m.job});if(!cfgCache||Date.now()-cfgTime>2000){cfgCache=await api('/status');cfgTime=Date.now()}r.speak=active.speak??cfgCache.speak;await chrome.storage.session.set({snapshot:r,snapshot_at:Date.now()});await chrome.storage.local.set({status:r.message});return r}
 if(content&&m.type==='prepare-line'&&m.job===active.job){const r=await api('/speech',{job:m.job,line_id:m.line_id});return r.error?{error:r.error}:{ready:!!r.audio,pending:!!r.pending}}
 if(content&&m.type==='timeline'&&m.job===active.job){if(!cfgCache||Date.now()-cfgTime>2000){cfgCache=await api('/status');cfgTime=Date.now()}const r=await audioTimeline({...m,config:{...cfgCache,voice:active.voice||cfgCache.voice,speak:active.speak??cfgCache.speak},target:'offscreen'});if(Date.now()-lastReport>1000){lastReport=Date.now();await api('/playback/report',{job:m.job,position:m.position,source_paused:!!m.paused,protocol:r?.protocol,speaking:!!r?.speaking,audio_time:r?.audio_time||0,audio_volume:r?.audio_volume||0,audio_muted:!!r?.audio_muted,error:r?.error||''}).catch(()=>{})}return r}
 if(content&&m.type==='timeline-stop'){if(m.job&&m.job!==active.job)return {ok:true};if(await chrome.offscreen.hasDocument())await chrome.runtime.sendMessage({target:'offscreen',type:'timeline-stop'});return {ok:true}}
 if(audio&&m.type==='speech'&&m.job===active?.job)return await api('/speech',{job:m.job,line_id:m.line_id,voice:m.voice});
 if(audio&&m.type==='audio'&&active?.mode==='capture'&&active.tabId===m.tabId)return await api('/audio',Uint8Array.from(atob(m.audio),c=>c.charCodeAt(0)),true);
 if(audio&&m.type==='capture-buffer'&&active?.mode==='capture'&&active.tabId===m.tabId){await chrome.tabs.sendMessage(active.tabId,{type:'ligter-capture-buffer',paused:!!m.paused}).catch(()=>{});return {ok:true}}
 if(audio&&m.type==='subtitle'&&active?.tabId===m.tabId){await chrome.tabs.sendMessage(active.tabId,{type:'ligter-line',text:m.text,source:m.source}).catch(()=>{});await chrome.storage.local.set({status:m.error||'Đang dịch…'});return {ok:true}}
 if(audio&&m.type==='ended'){await stop();return {ok:true}}
 if((panel||popup)&&m.type==='panel-state'){const {snapshot,snapshot_at}=await chrome.storage.session.get(['snapshot','snapshot_at']);const {status}=await chrome.storage.local.get('status');return {snapshot:snapshot?.id===active?.job?snapshot:null,snapshot_at,active,status}}
 if((panel||popup)&&m.type==='play-prepared'){const {snapshot}=await chrome.storage.session.get('snapshot');if(!active||snapshot?.id!==active.job||!(active.wait_full?snapshot.progress?.ready:snapshot.progress?.can_play))throw Error('Video chưa chuẩn bị xong.');const played=await chrome.tabs.sendMessage(active.tabId,{type:'ligter-play-prepared'});if(played?.error)throw Error(played.error);return {message:'Đang phát bản dịch đã chuẩn bị.'}}
 if(panel&&m.type==='seek'&&active){await chrome.tabs.sendMessage(active.tabId,{type:'ligter-v6-seek',position:m.position});return {ok:true}}
 if(panel&&m.type==='toggle'&&active){await chrome.tabs.sendMessage(active.tabId,{type:'ligter-v6-toggle'});return {ok:true}}
 if(panel&&m.type==='save'&&active?.job)return await api('/jobs/save',{job:active.job});
 if((panel||popup)&&m.type==='voice'){if(active&&(m.voice!==undefined||m.speak!==undefined||m.translation_style!==undefined))throw Error('Hủy bản chuẩn bị trước khi đổi giọng hoặc cách dịch.');cfgCache=null;return await api('/preferences',{voice:m.voice,speak:m.speak,subtitles:m.subtitles,bilingual:m.bilingual,translation_style:m.translation_style,playback_mode:m.playback_mode})}
 throw Error('Yêu cầu không hợp lệ hoặc phiên đã dừng.');
 })().then(respond).catch(e=>{chrome.storage.local.set({status:e.message});respond({error:e.message})});return true});
chrome.tabs.onRemoved.addListener(async id=>{if((await getActive())?.tabId===id)stop().catch(()=>{})});
chrome.tabs.onUpdated.addListener(async(id,change)=>{const active=await getActive();if(active?.tabId===id&&change.status==='loading')await stop()});
