"""CPU fallback for network ASR failures, with real word-level timestamps."""
import io
import re
import threading
import wave
from local_speech import HOME


def has_recognition_loop(text):
    """Detect a segment made almost entirely of a short repeated phrase."""
    # Split Han runs individually so punctuation-free repeats can be checked.
    tokens=re.findall(r'[\u3400-\u9fff]|[^\W_\u3400-\u9fff]+',str(text).casefold())
    for width in range(1,min(4,len(tokens)//8)+1):
        phrase=tokens[:width]
        if sum(token==phrase[i%width] for i,token in enumerate(tokens))>=len(tokens)*.95:
            return True
    return False


class LocalRecognizer:
    def __init__(self):
        self.model=None;self.lock=threading.RLock();self.state='cold'

    def warm(self):
        with self.lock:
            if self.model is not None:return
            self.state='loading'
            try:
                from faster_whisper import WhisperModel
                self.model=WhisperModel(str(HOME/'models'/'Whisper-small'),device='cpu',compute_type='int8',
                                        cpu_threads=4,num_workers=1,local_files_only=True)
                self.state='ready'
            except Exception:
                self.state='error';raise

    def start(self):
        with self.lock:
            if self.state!='cold':return
            self.state='loading'
        def load():
            try:self.warm()
            except Exception:pass
        threading.Thread(target=load,daemon=True,name='asr-warmup').start()

    def recognize(self,raw,language):
        with self.lock:
            self.warm()
            import numpy as np
            with wave.open(io.BytesIO(raw)) as source:
                if source.getframerate()!=16000 or source.getnchannels()!=1 or source.getsampwidth()!=2:
                    raise ValueError('Nhận diện tại máy cần PCM 16 kHz mono.')
                samples=np.frombuffer(source.readframes(source.getnframes()),dtype='<i2').astype('float32')/32768
            def decode(vad,recovery=False):
                options=dict(language=None if language=='auto' else language,beam_size=5 if recovery else 3,
                    word_timestamps=True,vad_filter=vad,condition_on_previous_text=False,temperature=0)
                if vad:options['vad_parameters']={'threshold':.35,'min_silence_duration_ms':400,'speech_pad_ms':350}
                segments,info=self.model.transcribe(samples,**options)
                out={'words':[],'segments':[],'language':info.language}
                for segment in segments:
                    if has_recognition_loop(segment.text):
                        out['uncertain_audio']=True
                        continue
                    confidence=float(segment.avg_logprob);no_speech=float(segment.no_speech_prob)
                    if recovery and (confidence<-.8 or float(segment.compression_ratio)>2.4 or no_speech>.8 and confidence<-.3):continue
                    out['segments'].append({'start':segment.start,'end':segment.end,'text':segment.text,
                        'no_speech_prob':no_speech,'avg_logprob':confidence,'compression_ratio':float(segment.compression_ratio)})
                    for word in segment.words or []:
                        out['words'].append({'start':word.start,'end':word.end,'word':word.word})
                return out
            result=decode(True)
            energy=float(np.sqrt(np.mean(samples*samples))) if len(samples) else 0
            if not result['words'] and not any(s['text'].strip() for s in result['segments']) and (energy>.001 or result.get('uncertain_audio')):
                # Audit an empty recognition once without the speech gate. Low
                # confidence results remain unresolved rather than becoming dialogue.
                recovered=decode(False,True);recovered['recovery_attempted']=True
                recovered['uncertain_audio']=bool(recovered.get('uncertain_audio')) or not bool(recovered['words'] or recovered['segments'])
                result=recovered
            return result
