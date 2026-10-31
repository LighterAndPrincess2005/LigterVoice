"""Measured preparation progress; coverage is not a promise of transcript accuracy."""
import math
import time


def clock(seconds):
    seconds=max(0,int(seconds or 0))
    return f'{seconds//3600}:{seconds//60%60:02}:{seconds%60:02}' if seconds>=3600 else f'{seconds//60:02}:{seconds%60:02}'


def job_progress(job,speech=None,now=None):
    now=time.monotonic() if now is None else now
    duration=float(job.get('duration') or 0)
    if not math.isfinite(duration) or duration<0:duration=0
    merged=[]
    ranges=[]
    for interval in job.get('coverage',[]):
        if not isinstance(interval,(list,tuple)) or len(interval)!=2:continue
        a,b=map(float,interval)
        if not math.isfinite(a) or not math.isfinite(b):continue
        a=max(0,a);b=min(b,duration) if duration else b
        if b>a:ranges.append((a,b))
    for a,b in sorted(ranges):
        if merged and a<=merged[-1][1]:merged[-1][1]=max(b,merged[-1][1])
        else:merged.append([a,b])
    processed=sum(b-a for a,b in merged)
    metrics=job.get('metrics',{});speech=speech or {'ready':0,'total':len(job.get('lines',[])),'pending':0,'failed':0,'enabled':False}
    state=job.get('state','preparing');phase=job.get('phase','audio')
    uncertain=len(metrics.get('uncertain_asr_windows',[]))
    full=duration>0 and processed>=duration-.05
    voice_done=not speech['enabled'] or speech['ready']>=speech['total']
    ready=state=='ready' and full and voice_done and not speech['failed']
    done=ready and not uncertain
    if state in ('error','cancelled'):phase=state
    elif uncertain and state=='ready':phase='review'
    elif speech['failed']:phase='speech_error'
    elif state=='waiting':phase='service_wait'
    elif done:phase='done'
    elif state=='buffered':phase='waiting'
    elif state=='ready':phase='speech' if speech['pending'] else 'speech_waiting'
    labels={'audio':'Đang lấy audio','recognize':'Đang nhận diện lời nói','translate':'Đang dịch sang tiếng Việt',
            'speech':'Đang chuẩn bị giọng đọc','waiting':'Đã đệm phần đang xem · chờ video phát tiếp',
            'speech_waiting':'Đã xử lý phần chữ · giọng được chuẩn bị theo đoạn xem',
            'done':'Đã chuẩn bị xong','review':'Có đoạn âm thanh cần kiểm tra lại',
            'error':'Xử lý bị lỗi','speech_error':'Có câu chưa tạo được giọng','cancelled':'Đã dừng','service_wait':'Đang chờ dịch vụ phản hồi'}
    phase_seconds=max(0,int(now-job.get('phase_since',job.get('created',now))))
    return {'phase':phase,'label':labels.get(phase,'Đang xử lý'),'percent':round(min(100,processed/duration*100),1) if duration else None,
            'processed_seconds':round(processed,2),'total_seconds':duration,
            'coverage_text':f'Đã xử lý {clock(processed)} / {clock(duration)} audio' if duration else 'Đang xác định thời lượng audio',
            'interval_text':f"{clock(job.get('processing_from',0))}–{clock(job.get('processing_to',0))}" if phase in ('audio','recognize','translate') and job.get('processing_to',0)>job.get('processing_from',0) else '',
            'speech':speech,'phase_seconds':phase_seconds,'elapsed_seconds':max(0,int(now-job.get('created',now))),
            'media_bytes':metrics.get('media_bytes',0),'uncertain_windows':uncertain,
            'indeterminate':not duration or processed==0 and state not in ('error','cancelled','ready'),
            'done':done,'ready':ready,'can_play':ready,'quality_ok':not uncertain,'error':job.get('error','') if state=='error' else '',
            'message':job.get('message','')}
