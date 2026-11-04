/* Runs in the page world; publishes video metadata, never credentials. */
(()=>{
 if(window.__ligterMediaHook)return;window.__ligterMediaHook=true;
 const seen=new Map(),sizes=new Map();
 const urls=value=>{if(typeof value==='string')return value.startsWith('https://')?[value]:[];if(Array.isArray(value))return value.flatMap(urls);if(value&&typeof value==='object')return ['url_list','urlList','main_url','backup_url','fallback_url','src','url','Url'].flatMap(k=>urls(value[k]));return []};
 function clip(item){
  const id=String(item.aweme_id||item.awemeId||'');if(!/^\d{15,22}$/.test(id))return;
  const v=item.video||{};const tracks=v.bit_rate_audio||v.bitRateAudioList||[];
  const audios=[...tracks].sort((a,b)=>(Number((a.audio_meta||a.audioMeta||a).bitrate)||0)-(Number((b.audio_meta||b.audioMeta||b).bitrate)||0));
  const audio=audios.flatMap(a=>urls(a.audio_meta||a.audioMeta||a));
  const rates=[...(v.bit_rate||v.bitRateList||[])].filter(x=>x.format!=='dash').sort((a,b)=>(a.bit_rate||a.bitRate||0)-(b.bit_rate||b.bitRate||0));
  const videos=[...new Set([...rates.flatMap(a=>urls(a.play_addr||a.playAddr)),...urls(v.play_addr||v.playAddr)])].filter(x=>x.length<5000).slice(0,5);
  const sources=[...new Set([...audio,...videos])].filter(x=>x.length<5000).slice(0,5);
  const duration=Number(v.duration||item.duration||0)/1000;
  const cla=v.cla_info||v.claInfo||{};
  const captions=[cla.caption_infos,cla.captionInfos,v.subtitle_infos,v.subtitleInfos,v.subtitle?.subtitleInfos,item.subtitle_infos]
    .flatMap(list=>Array.isArray(list)?list:[])
    .filter(track=>{const lang=String(track?.lang||track?.language_code||track?.LanguageCodeName||track?.languageCodeName||'');return !lang||/^(zh|cmn|en)(-|_|$)/i.test(lang)})
    .sort((a,b)=>Number(/^(zh|cmn)/i.test(String(b.lang||b.LanguageCodeName||b.language_code||'')))-Number(/^(zh|cmn)/i.test(String(a.lang||a.LanguageCodeName||a.language_code||''))))
    .flatMap(urls).filter(url=>url.length<4000);
  const caption_urls=[...new Set([...captions,...(seen.get(id)?.caption_urls||[])])].slice(0,2);
  if(sources.length||caption_urls.length){const c={id,sources:sources.length?sources:seen.get(id)?.sources||[],videos,duration,caption_urls,title:String(item.desc||item.description||'').slice(0,300)};seen.set(id,c);if(seen.size>100)seen.delete(seen.keys().next().value);window.postMessage({type:'LIGTER_MEDIA',clips:[c]},location.origin)}
 }
 function scan(value,depth=0){if(!value||typeof value!=='object'||depth>9)return;if(value.aweme_id||value.awemeId){clip(value);return}for(const x of Object.values(value))scan(x,depth+1)}
 const relevant=url=>/\/aweme\/v\d+\/web\//.test(String(url));
 const originalFetch=window.fetch;window.fetch=async function(...args){const response=await originalFetch.apply(this,args);if(relevant(response.url))response.clone().json().then(value=>scan(value)).catch(()=>{});return response};
 async function readRange(m){
  if(!/^[\w-]{20,80}$/.test(String(m.id))||!/^bytes=(?:\d+-\d+|-\d+)$/.test(m.range||''))return;
  const allowed=url=>{const p=new URL(url);return p.protocol==='https:'&&!p.username&&!p.password&&(!p.port||p.port==='443')&&/(^|\.)(douyinvod\.com|douyin\.com|zjcdn\.com|bytecdn\.cn|bytecdn\.com|byteimg\.com|bytedance\.com|ixigua\.com|tiktokcdn\.com|akamaized\.net|bilivideo\.com|hdslb\.com)$/.test(p.hostname)};
  const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),8000);let reader;
  try{
   if(!allowed(m.url))throw Error('Nguồn audio không được phép.');
   const r=await originalFetch.call(window,m.url,{headers:{Range:m.range},credentials:'omit',mode:'cors',signal:controller.signal});
   if(!r.ok||!allowed(r.url||m.url))throw Error('CDN trả lỗi '+r.status);
   const range=r.headers.get('Content-Range');let total=range?.match(/\/(\d+)$/)?.[1]||sizes.get(m.url);
   if(!total&&r.status===200)total=r.headers.get('Content-Length');
   if(!total&&r.status===206){const head=await originalFetch.call(window,m.url,{method:'HEAD',credentials:'omit',mode:'cors',signal:controller.signal});if(!head.ok||!allowed(head.url||m.url))throw Error('CDN chưa trả kích thước audio.');total=head.headers.get('Content-Length')}
   const requestedStart=m.range.match(/^bytes=(\d+)-/)?.[1];
   const start=range?.match(/^bytes (\d+)-/)?.[1]||requestedStart||String(Math.max(0,Number(total)-Number(m.range.slice(7))));
   if(r.status===200&&!/^bytes=0-/.test(m.range))throw Error('CDN không hỗ trợ đọc từng phần.');
   if(!total||!/^\d+$/.test(total))throw Error('CDN chưa cung cấp kích thước audio.');
   sizes.set(m.url,total);if(sizes.size>100)sizes.delete(sizes.keys().next().value);
   reader=r.body.getReader();const chunks=[];let size=0;
   while(size<1048576){const {done,value}=await reader.read();if(done)break;const part=value.subarray(0,1048576-size);chunks.push(part);size+=part.length}
   await reader.cancel();if(!size)throw Error('Phần audio rỗng.');
   let binary='';for(const chunk of chunks)for(let i=0;i<chunk.length;i+=16384)binary+=String.fromCharCode(...chunk.subarray(i,i+16384));
   window.postMessage({type:'LIGTER_RANGE_RESULT',id:m.id,status:206,body:btoa(binary),headers:{'Content-Length':String(size),'Content-Range':`bytes ${start}-${Number(start)+size-1}/${total}`,'Accept-Ranges':'bytes','Content-Type':r.headers.get('Content-Type')||'application/octet-stream'}},location.origin);
  }catch(error){console.warn('Ligter Voice audio range:',error.message);window.postMessage({type:'LIGTER_RANGE_RESULT',id:m.id,error:error.message},location.origin)}
  finally{clearTimeout(timer);reader?.cancel().catch(()=>{})}
 }
 const originalOpen=XMLHttpRequest.prototype.open;XMLHttpRequest.prototype.open=function(method,url,...args){if(relevant(url))this.addEventListener('load',()=>{try{scan(this.responseType==='json'?this.response:JSON.parse(this.responseText))}catch{}});return originalOpen.call(this,method,url,...args)};
 function initial(){for(const id of ['RENDER_DATA','__UNIVERSAL_DATA_FOR_REHYDRATION__']){const raw=document.getElementById(id)?.textContent;if(raw){try{scan(JSON.parse(raw))}catch{try{scan(JSON.parse(decodeURIComponent(raw)))}catch{}}}}}
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',initial,{once:true});else initial();
 window.addEventListener('message',e=>{if(e.source!==window)return;if(e.data?.type==='LIGTER_RANGE_REQUEST'){readRange(e.data);return}if(e.data?.type!=='LIGTER_REQUEST_MEDIA')return;const id=String(e.data.id||'');if(seen.has(id)){window.postMessage({type:'LIGTER_MEDIA',clips:[seen.get(id)]},location.origin);if(seen.get(id).caption_urls.length)return}if(!/^\d{15,22}$/.test(id))return;
  const element=document.querySelector(`[data-e2e-vid="${id}"]`);if(!element)return;const key=Object.keys(element).find(x=>x.startsWith('__reactFiber$'));let fiber=key?element[key]:null;for(let i=0;fiber&&i<28;i++,fiber=fiber.return){scan(fiber.memoizedProps,5);if(seen.get(id)?.caption_urls?.length)break}
 });
})();
