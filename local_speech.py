"""Vietnamese voices generated locally using the MIT licensed ZeroTTS model."""
import io
from pathlib import Path
import subprocess
import sys
import threading
import time
import wave
import imageio_ffmpeg


HOME = Path(sys.executable).parent if getattr(sys,'frozen',False) else Path(__file__).parent


class LocalSpeech:
    def __init__(self, events):
        self.events=events
        self.model=None
        self.lock=threading.RLock()
        self.state='cold'
        self.error=''
        self.last_timing={}

    @property
    def directory(self):
        quantized=HOME/'models'/'ZeroTTS-int8'
        return quantized if (quantized/'READY').exists() else HOME/'models'/'ZeroTTS-fp32'

    def warm(self):
        with self.lock:
            if self.model is not None:return
            self.state='loading'
            try:
                from zerotts import ZeroTTS
                import json,onnxruntime as ort
                started=time.monotonic()
                self.model=ZeroTTS.from_pretrained(self.directory,local_files_only=True,
                    intra_op_num_threads=4,codec_intra_op_num_threads=2,warmup=False)
                # The default ORT CPU arena retains every growing autoregressive
                # allocation. Replace sessions before their first inference so a
                # long viewing session cannot retain several GB of scratch space.
                def bounded(path,threads):
                    options=ort.SessionOptions();options.intra_op_num_threads=threads;options.inter_op_num_threads=1
                    options.enable_cpu_mem_arena=False;options.enable_mem_pattern=False
                    options.graph_optimization_level=ort.GraphOptimizationLevel.ORT_ENABLE_ALL
                    return ort.InferenceSession(str(path),sess_options=options,providers=['CPUExecutionProvider'])
                for name in ('prefix_step','local_frame_decode','text_encoder'):
                    setattr(self.model,name+'_sess',bounded(self.directory/'onnx'/(name+'.onnx'),4))
                codec=self.directory/'onnx'/'codec';meta=json.loads((codec/'codec_browser_onnx_meta.json').read_text(encoding='utf-8'))
                self.model.codec._decode_step_sess=bounded(codec/meta['files']['decode_step'],2)
                # Full-waveform codec attention is unnecessary: render() always
                # decodes short streaming blocks with a bounded codec KV state.
                self.model.codec._decode_full_sess=None
                self.model.warmup()
                self.model.load_voice('quangminh')
                self.model.load_voice('baotrang')
                self.state='ready';self.error=''
                self.events.put(f'Giọng đọc tại máy đã sẵn sàng ({time.monotonic()-started:.1f}s).')
            except Exception:
                self.state='error';self.error='Chưa mở được bộ giọng tại máy. Chọn giọng trực tuyến trong Cài đặt để tiếp tục.'
                self.events.put(self.error)
                raise ValueError(self.error)

    def start(self):
        if self.state!='cold':return
        def load():
            try:self.warm()
            except ValueError:pass
        threading.Thread(target=load,daemon=True,name='voice-warmup').start()

    def render(self,text,voice,path,cancel=None):
        # One inference at a time avoids competing for DDR memory bandwidth.
        with self.lock:
            def check():
                if cancel is not None and cancel.is_set():
                    from concurrent.futures import CancelledError
                    raise CancelledError('Video đã chuyển hoặc đã dừng.')
            check()
            self.warm()
            import numpy as np
            from zerotts import normalize_vi_text
            from zerotts.chunking import chunk_text,normalize_punctuation,clean_segment_punctuation
            selected='quangminh' if 'NamMinh' in voice else 'baotrang'
            timing={};started=time.monotonic()
            parts=chunk_text(normalize_punctuation(normalize_vi_text(text)),max_chunk_sec=6)
            generated=[]
            for part in parts:
                check()
                part=clean_segment_punctuation(part)
                if not part.strip():continue
                if generated:generated.append(np.zeros(int(self.model.sample_rate*.06),dtype=np.float32))
                for block in self.model.synthesize_stream(part,voice=selected,first_chunk_frames=8,max_chunk_frames=16):
                    check()
                    generated.append(np.asarray(block).reshape(-1))
            samples=np.concatenate(generated) if generated else np.zeros(0,dtype=np.float32)
            if not len(samples):raise ValueError('Giọng tại máy chưa tạo được âm thanh.')
            check()
            wav=io.BytesIO()
            with wave.open(wav,'wb') as f:
                f.setnchannels(1);f.setsampwidth(2);f.setframerate(self.model.sample_rate)
                f.writeframes((np.clip(samples,-1,1)*32767).astype('<i2').tobytes())
            tmp=path.with_suffix('.encoding.mp3')
            command=[imageio_ffmpeg.get_ffmpeg_exe(),'-hide_banner','-loglevel','error','-y','-i','pipe:0',
                     '-codec:a','libmp3lame','-q:a','4',str(tmp)]
            result=subprocess.run(command,input=wav.getvalue(),stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                                  timeout=20,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            if result.returncode:raise ValueError('Không đóng gói được giọng đọc tại máy.')
            tmp.replace(path)
            self.last_timing={'voice':selected,'seconds':round(time.monotonic()-started,3),
                              'audio_seconds':round(len(samples)/self.model.sample_rate,3),'parts':len(parts)}
            return path
