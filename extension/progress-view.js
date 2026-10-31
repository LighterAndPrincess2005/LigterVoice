/* Shared, text-only rendering for popup and transcript panel. Never invent percent. */
(()=>{
 const time=s=>{s=Math.max(0,Math.floor(Number(s)||0));return `${Math.floor(s/60)}:${String(s%60).padStart(2,'0')}`};
 window.LigterProgress={render(root,p,{stale=false}={}){
  if(!root)return;root.hidden=!p;if(!p)return;
  root.classList.toggle('failed',!!p.error||p.phase==='speech_error');root.classList.toggle('complete',!!p.done);root.classList.toggle('review',p.uncertain_windows>0);
  root.querySelector('.progress-phase').textContent=stale?'Mất cập nhật từ video':p.label;
  const bar=root.querySelector('progress');
  if(p.indeterminate&&!stale)bar.removeAttribute('value');else bar.value=p.percent??0;
  bar.setAttribute('aria-label','Phần audio đã xử lý');
  root.querySelector('.progress-percent').textContent=p.indeterminate?'…':p.percent===null?'':`${Math.floor(p.percent)}%`;
  root.querySelector('.progress-coverage').textContent=p.coverage_text;
  const parts=[];if(p.can_play&&!p.ready)parts.push(`Đã đệm ${Math.floor(p.playable_seconds||0)} giây có giọng`);if(p.phase==='audio'&&p.media_bytes)parts.push(`Đã nhận ${(p.media_bytes/1048576).toFixed(1)} MB`);if(p.phase==='service_wait'&&p.message)parts.push(p.message);if(p.uncertain_windows)parts.push(`${p.uncertain_windows} đoạn cần kiểm tra`);if(p.interval_text&&!p.done)parts.push('Đoạn '+p.interval_text);
  if(p.speech?.enabled)parts.push(`Giọng ${p.speech.ready}/${p.speech.total} câu`+(p.speech.failed?` · ${p.speech.failed} lỗi`:''));
  if(!p.done&&!['waiting','error','cancelled'].includes(p.phase))parts.push(`Đang ở bước này ${time(p.phase_seconds)}`);
  root.querySelector('.progress-detail').textContent=p.error||(stale?'Chưa nhận được trạng thái mới. Kiểm tra kết nối với app.':parts.join(' · '));
 }};
})();
