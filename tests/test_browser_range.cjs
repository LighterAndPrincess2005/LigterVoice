const assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
(async()=>{
 const messages=[],network=[];let listener,mode='large';
 const window={postMessage:m=>messages.push(m),addEventListener:(type,fn)=>listener=fn,fetch:async(url,options)=>{
  network.push({url,options});if(mode==='cors')throw Error('CORS refused');
  const size=mode==='large'?1049000:100;const r=options?.method==='HEAD'?new Response(null,{headers:{'Content-Length':'2000'}}):new Response(new Uint8Array(size).fill(7),{status:mode==='large'?200:206,headers:{'Content-Length':String(size),...(['large','hidden'].includes(mode)?{}:{'Content-Range':'bytes 100-199/2000'})}});
  Object.defineProperty(r,'url',{value:url});return r;
 }};
 class XHR{}XHR.prototype.open=()=>{};
 vm.runInNewContext(fs.readFileSync('extension/media-hook.js','utf8'),{window,XMLHttpRequest:XHR,document:{readyState:'complete',getElementById:()=>null},location:{origin:'https://www.douyin.com'},URL,AbortController,setTimeout,clearTimeout,btoa:s=>Buffer.from(s,'binary').toString('base64')});
 const request=async(id,url,range)=>{listener({source:window,data:{type:'LIGTER_RANGE_REQUEST',id,url,range}});for(let i=0;i<20&&!messages.some(m=>m.id===id);i++)await new Promise(r=>setImmediate(r));return messages.find(m=>m.id===id)};
 const large=await request('abcdefghijklmnopqrst1','https://a.douyinvod.com/a','bytes=0-1048575');assert.equal(Buffer.from(large.body,'base64').length,1048576);assert.equal(large.headers['Content-Range'],'bytes 0-1048575/1049000');assert.equal(network[0].options.credentials,'omit');assert.equal(network[0].options.mode,'cors');
 mode='small';const part=await request('abcdefghijklmnopqrst2','https://a.douyinvod.com/a','bytes=100-199');assert.equal(part.headers['Content-Range'],'bytes 100-199/2000');
 mode='hidden';const hidden=await request('abcdefghijklmnopqrst5','https://a.douyinvod.com/hidden','bytes=100-199');assert.equal(hidden.headers['Content-Range'],'bytes 100-199/2000','recover range size with a normal CORS HEAD when Content-Range is not exposed');
 const count=network.length;const denied=await request('abcdefghijklmnopqrst3','https://127.0.0.1/secret','bytes=0-10');assert(denied.error);assert.equal(network.length,count,'page messages cannot turn the relay into a private-network fetcher');
 mode='cors';const failed=await request('abcdefghijklmnopqrst4','https://a.douyinvod.com/a','bytes=0-10');assert(failed.error,'CORS errors propagate without bypassing browser protections');
 console.log('PASS browser-origin media ranges, bounded memory, original range headers, no cookies, CDN allowlist and explicit CORS failure');
})().catch(error=>{console.error(error);process.exitCode=1});
