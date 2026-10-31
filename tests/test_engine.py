import concurrent.futures
import io
import json
import queue
import sys
import tempfile
import time
import unittest
import wave
from pathlib import Path
from unittest.mock import patch, Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from engine import Engine, public_media_url, srt_text, sentence_segments, soniox_sentences, aligned_semantic_lines, repeated_line, Cancelled, validate_translation

def response(data):
    r=Mock(ok=True)
    r.json.return_value=data
    return r

class PipelineTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.cfg={'key':'fake-key','provider':'groq','language':'zh','model':'llama-3.3-70b-versatile','speak':False,'voice':'vi-VN-NamMinhNeural'}
        self.e=Engine(self.tmp.name,lambda:self.cfg,queue.Queue())
    def tearDown(self):
        self.e.close()
        self.e.pool.shutdown(wait=True,cancel_futures=True)
        self.e.translation_pool.shutdown(wait=True,cancel_futures=True)
        self.e.speech_pool.shutdown(wait=True,cancel_futures=True)
        self.tmp.cleanup()
    def media(self):
        p=Path(self.tmp.name)/'source.wav'
        with wave.open(str(p),'wb') as f:
            f.setnchannels(1);f.setsampwidth(2);f.setframerate(16000);f.writeframes(b'\x00\x00'*16000*4)
        return p
    def job(self):
        return {'cancel':__import__('threading').Event()}
    def test_decoder_real_ffmpeg(self):
        raw=self.e.decode(self.media(),1,2,self.job())
        with wave.open(io.BytesIO(raw)) as f:
            self.assertEqual(f.getframerate(),16000)
            self.assertEqual(f.getnchannels(),1)
            self.assertAlmostEqual(len(f.readframes(32000))/32000,2,places=1)
    def test_cancel_decode(self):
        j=self.job();j['cancel'].set()
        with self.assertRaises(Cancelled):
            self.e.decode(self.media(),0,1,j)
    def test_timestamp_and_translation_mapping(self):
        a=response({'segments':[{'start':.1,'end':1.4,'text':'你好','no_speech_prob':.1},{'start':1.5,'end':3,'text':'Welcome','no_speech_prob':.1}]})
        b=response({'choices':[{'message':{'content':json.dumps({'translations':[{'id':1,'text':'Chào mừng'},{'id':0,'text':'Xin chào'}]})}}]})
        with patch('engine.HttpClient.post',side_effect=[a,b]):
            lines=self.e.groq(b'WAV',self.cfg,16,20)
        self.assertEqual(lines[0]['translation'],'Xin chào')
        self.assertEqual(lines[1]['translation'],'Chào mừng')
        self.assertEqual(lines[0]['start'],16.1)
    def test_missing_translation_rejected(self):
        a=response({'segments':[{'start':0,'end':1,'text':'Hello'}]})
        b=response({'choices':[{'message':{'content':'{"translations":[]}'}}]})
        with patch('engine.HttpClient.post',side_effect=[a,b]),self.assertRaises(ValueError):
            self.e.groq(b'WAV',self.cfg,0,1)

    def test_transient_asr_failure_retries_without_losing_audio(self):
        unavailable=Mock(ok=False,status_code=503)
        recognized=response({'segments':[{'start':0,'end':1,'text':'Hello!'}]});recognized.status_code=200
        translated=response({'choices':[{'message':{'content':'{"translations":[{"id":0,"text":"Xin chào!"}]}'}}]})
        with patch('engine.HttpClient.post',side_effect=[unavailable,recognized,translated]) as post,patch('engine.time.sleep'):
            lines=self.e.groq(b'original-audio',self.cfg,0,1)
        self.assertEqual(lines[0]['translation'],'Xin chào!')
        self.assertEqual(post.call_args_list[0].kwargs['files'],post.call_args_list[1].kwargs['files'])

    def test_network_asr_failure_uses_local_recognition(self):
        import requests
        recognized={'segments':[{'start':0,'end':1,'text':'Hello!'}]}
        translated=response({'choices':[{'message':{'content':'{"translations":[{"id":0,"text":"Xin chào!"}]}'}}]})
        with patch('engine.HttpClient.post',side_effect=[requests.Timeout(),requests.Timeout(),translated]),patch('engine.time.sleep'),patch.object(self.e.local_asr,'recognize',return_value=recognized) as local:
            self.assertEqual(self.e.groq(b'original',self.cfg,0,1)[0]['translation'],'Xin chào!')
            local.assert_called_once_with(b'original','zh')

    def test_incomplete_boundary_word_waits_for_continuation(self):
        source=self.media();observed=[]
        def recognize(raw,cfg,start,end):
            observed.append([x['source'] for j in self.e.jobs.values() for x in j['lines']])
            if start==0:return [{'start':9.5,'end':10.5,'source':'你','translation':'Anh','complete':False}]
            if start<10:return [{'start':9.5,'end':12,'source':'你做什么工作？','translation':'Anh làm công việc gì?','complete':True}]
            return []
        with patch('engine.public_media_url',side_effect=lambda x:x),patch.object(self.e,'source',return_value=source),patch.object(self.e,'decode',return_value=b'WAV'),patch.object(self.e,'transcribe',side_effect=recognize):
            r=self.e.start({'video_id':'continuation','duration':30,'sources':['https://test.douyinvod.com/a']})
            deadline=time.monotonic()+3
            while self.e.snapshot(r['job'])['state'] not in ('ready','error') and time.monotonic()<deadline:time.sleep(.01)
            snap=self.e.snapshot(r['job'])
        self.assertEqual(snap['state'],'ready',snap)
        self.assertEqual([x['source'] for x in snap['lines']],['你做什么工作？'])
        self.assertFalse(any('你' in words for words in observed))
        self.assertEqual(snap['coverage'][:2],[[0,9.5],[9.5,20]])

    def test_local_file_pipeline_uses_selected_file_without_copy(self):
        source=self.media()
        with patch.object(self.e,'transcribe',return_value=[{'start':0,'end':1,'source':'hello','translation':'xin chào'}]):
            result=self.e.start_file(source)
            deadline=time.monotonic()+3
            while self.e.snapshot(result['job'])['state'] not in ('ready','error') and time.monotonic()<deadline:time.sleep(.02)
        snapshot=self.e.snapshot(result['job'])
        self.assertEqual(snapshot['state'],'ready',snapshot)
        self.assertEqual(snapshot['metrics']['media_source'],'local_file')
        self.assertAlmostEqual(snapshot['duration'],4)
    def test_url_restricts_private_and_other_hosts(self):
        for url in ['http://127.0.0.1/x','https://evil.example/x','https://douyin.com@127.0.0.1/x','https://www.douyin.com:123/x']:
            with self.assertRaises(ValueError):public_media_url(url)
        with patch('engine.socket.getaddrinfo',return_value=[(2,1,6,'',('127.0.0.1',443))]),self.assertRaises(ValueError):
            public_media_url('https://www.douyin.com/x')
    def test_observed_douyin_zjcdn_sources(self):
        with patch('engine.socket.getaddrinfo',return_value=[(2,1,6,'',('8.8.8.8',443))]):
            self.assertEqual(public_media_url('https://v5-dy-ov-experiment.zjcdn.com/a'),'https://v5-dy-ov-experiment.zjcdn.com/a')
    def test_job_pipeline_seek_priority_cache_and_export(self):
        self.cfg['preload_all']=True
        source=self.media()
        starts=[]
        def recognize(raw,cfg,start,end):
            starts.append(start)
            aligned=round((start+2)/10)*10 if start else 0
            return [{'start':aligned,'end':aligned+2,'source':'hello','translation':'xin chào'}]
        with patch('engine.public_media_url',side_effect=lambda x:x),patch.object(self.e,'source',return_value=source),patch.object(self.e,'decode',return_value=b'WAV'),patch.object(self.e,'transcribe',side_effect=recognize):
            r=self.e.start({'video_id':'1234567890123456789','owner':'test','position':33,'duration':240,'sources':['https://test.douyinvod.com/a'],'title':'Test'})
            self.e.pool.submit(lambda:None).result(timeout=10)
            deadline=time.monotonic()+3
            while self.e.snapshot(r['job'])['state'] not in ('ready','error') and time.monotonic()<deadline:time.sleep(.02)
            snap=self.e.snapshot(r['job'])
            self.assertEqual(snap['state'],'ready',snap)
            self.assertEqual(starts[0],28)
            self.assertEqual(sorted(snap['windows']),list(range(24)))
            self.e.save(r['job'])
            self.assertEqual(len(list((Path(self.tmp.name)/'GhiChu').glob('*.srt'))),1)
            r2=self.e.start({'video_id':'1234567890123456789','owner':'test','duration':240,'sources':['https://test.douyinvod.com/a']})
            self.assertEqual(r2['cached_lines'],len(snap['lines']))
    def test_unsupported_first_source_does_not_hide_fallback(self):
        def check(url):
            if 'unknown.example' in url:raise ValueError('unsupported')
            return url
        with patch('engine.public_media_url',side_effect=check),patch.object(self.e.pool,'submit'):
            r=self.e.start({'video_id':'test-fallback','sources':['https://unknown.example/x','https://test.douyinvod.com/a'],'duration':60})
        self.assertEqual(self.e.find(r['job'])['urls'],['https://test.douyinvod.com/a'])
    def test_cdn_decode_retry_preserves_prior_dialogue_and_rotates_source(self):
        from engine import RemoteMedia
        import threading
        media=RemoteMedia.__new__(RemoteMedia);media.urls=['first','backup'];media.guard=threading.Lock();media.close=Mock()
        def recognize(raw,cfg,start,end):
            at=0 if start==0 else 10
            return [{'start':at,'end':at+1,'source':'hello '+str(at),'translation':'xin chào'}]
        with patch('engine.public_media_url',side_effect=lambda x:x),patch.object(self.e,'source',return_value=media),patch.object(self.e,'decode',side_effect=[b'WAV',ValueError('CDN timeout'),b'WAV']) as decode,patch.object(self.e,'transcribe',side_effect=recognize):
            r=self.e.start({'video_id':'cdn-retry','duration':20,'sources':['https://test.douyinvod.com/a']})
            deadline=time.monotonic()+4
            while self.e.snapshot(r['job'])['state'] not in ('ready','error') and time.monotonic()<deadline:time.sleep(.01)
            snap=self.e.snapshot(r['job'])
        self.assertEqual(snap['state'],'ready',snap);self.assertEqual([x['start'] for x in snap['lines']],[0,10])
        self.assertEqual(snap['metrics']['media_retries'],1);self.assertEqual(decode.call_count,3)
        self.assertEqual(media.urls,['backup','first']);media.close.assert_called_once()
    def test_new_video_does_not_reuse_cancelled_speech_work(self):
        import threading
        old_stop=threading.Event();new_stop=threading.Event()
        old=concurrent.futures.Future();new=concurrent.futures.Future()
        with patch.object(self.e.speech_pool,'submit',side_effect=[old,new]) as submit:
            self.assertIs(self.e.prefetch_speech('Same sentence','vi-VN-NamMinhNeural',old_stop),old)
            old_stop.set();self.e.cancel_speech(old_stop)
            self.assertTrue(old.cancelled())
            self.assertIs(self.e.prefetch_speech('Same sentence','vi-VN-NamMinhNeural',new_stop),new)
            self.assertEqual(submit.call_count,2)
    def test_natural_playback_progress_does_not_skip_unprocessed_audio(self):
        source=self.media();starts=[]
        def recognize(raw,cfg,start,end):
            starts.append(start)
            if len(starts)==1:
                jid=next(iter(self.e.jobs))
                for position in range(5,41,5):self.e.seek(jid,position)
            return []
        with patch('engine.public_media_url',side_effect=lambda x:x),patch.object(self.e,'source',return_value=source),patch.object(self.e,'decode',return_value=b'WAV'),patch.object(self.e,'transcribe',side_effect=recognize):
            r=self.e.start({'video_id':'natural-progress','duration':60,'sources':['https://test.douyinvod.com/a']})
            deadline=time.monotonic()+3
            while self.e.snapshot(r['job'])['state'] not in ('ready','error') and time.monotonic()<deadline:time.sleep(.01)
            snap=self.e.snapshot(r['job'])
        self.assertEqual(snap['state'],'ready',snap);self.assertEqual(starts,[0,8,38])
        self.assertEqual(sorted(snap['windows']),list(range(6)))
    def test_srt_hours_and_unicode(self):
        text=srt_text([{'start':3601.25,'end':3603,'translation':'Xin chào'}])
        self.assertIn('01:00:01,250 --> 01:00:03,000',text)
        self.assertIn('Xin chào',text)

    def test_nearby_rapid_speaker_turns_are_not_duplicates(self):
        a={'start':.1,'end':.6,'source':'你好。'}
        b={'start':.25,'end':.7,'source':'是。'}
        self.assertFalse(repeated_line(a,b))
        self.assertTrue(repeated_line(a,{'start':.12,'end':.61,'source':'你好!'}))
        self.assertFalse(repeated_line(a,{'start':.61,'end':.9,'source':'你好。'}))
    def test_short_chinese_sentence_and_pause(self):
        result={'words':[{'word':'你好','start':.1,'end':.6},{'word':'今天','start':1.4,'end':1.7},{'word':'天气','start':1.7,'end':2},{'word':'很好。','start':2,'end':2.5}]}
        segments=sentence_segments(result,10,26)
        self.assertEqual(len(segments),2)
        self.assertEqual(segments[0],{'start':10.1,'end':10.6,'source':'你好'})
        self.assertEqual(segments[1]['source'],'今天天气很好。')
    def test_english_sentences_not_forced_into_upload_window(self):
        result={'words':[{'word':'Hello!','start':0,'end':.4},{'word':'How','start':.5,'end':.7},{'word':'are','start':.7,'end':.9},{'word':'you?','start':.9,'end':1.2}]}
        segments=sentence_segments(result,0,16)
        self.assertEqual([x['source'] for x in segments],['Hello!','How are you?'])
        self.assertEqual(segments[0]['end'],.4)
    def test_soniox_endpoint_before_translation_preserves_source(self):
        tokens=[{'text':'你好','start_ms':100,'end_ms':600,'translation_status':'original'},
                {'text':'<end>'}, {'text':'Xin chào.','translation_status':'translation'}, {'text':'<end>'},
                {'text':'再见','start_ms':2200,'end_ms':2700,'translation_status':'original'},
                {'text':'Tạm biệt.','translation_status':'translation'},{'text':'<end>'}]
        lines=soniox_sentences(tokens,0,8)
        self.assertEqual([x['source'] for x in lines],['你好','再见'])
        self.assertEqual([x['translation'] for x in lines],['Xin chào.','Tạm biệt.'])
        self.assertEqual(lines[0]['end'],.6)
    def test_greeting_is_separate_even_when_asr_uses_comma(self):
        result={'words':[{'word':'你好,','start':.14,'end':.58},{'word':'今天','start':.6,'end':.9},{'word':'很好。','start':.9,'end':1.4}]}
        self.assertEqual([x['source'] for x in sentence_segments(result,0,3)],['你好,','今天很好。'])

    def test_model_boundaries_map_to_real_words_without_heuristic_split(self):
        words=[{'word':'你好,','start':.1,'end':.5},{'word':'今天','start':.52,'end':.9},{'word':'很好','start':.9,'end':1.4}]
        lines=aligned_semantic_lines(words,{'lines':[{'from':0,'translation':'Xin chào.'},{'from':1,'translation':'Hôm nay rất tốt.'}]},30,40)
        self.assertEqual([(x['start'],x['end']) for x in lines],[(30.1,30.5),(30.52,31.4)])
        self.assertEqual(lines[1]['source'],'今天很好')
        for starts in ([1],[0,0],[0,3],[0,True]):
            with self.assertRaises(ValueError):
                aligned_semantic_lines(words,{'lines':[{'from':i,'translation':'test'} for i in starts]},0,10)

    def test_translation_server_failure_switches_model_and_caches_success(self):
        limited=Mock(ok=False,status_code=503)
        valid=response({'choices':[{'message':{'content':'{"lines":[{"from":0,"translation":"Xin chào!","complete":true}]}'}}]})
        valid.status_code=200
        words=[{'word':'Hello!','start':0,'end':1}]
        with patch('engine.HttpClient.post',side_effect=[limited,valid]) as post,patch('engine.time.sleep'):
            first=self.e.translate_words(words,self.cfg,0,2)
            second=self.e.translate_words(words,self.cfg,0,2)
        self.assertEqual(first,second)
        self.assertEqual(post.call_count,2)
        self.assertEqual(first[0]['translation'],'Xin chào!')

    def test_rate_limit_obeys_retry_after_without_extra_requests(self):
        from engine import RateLimited
        limited=Mock(ok=False,status_code=429,headers={'retry-after':'9'})
        words=[{'word':'Hello!','start':0,'end':1}]
        with patch('engine.HttpClient.post',return_value=limited) as post:
            for _ in range(2):
                with self.assertRaises(RateLimited):self.e.translate_words(words,self.cfg,0,2)
            self.assertEqual(post.call_count,1)

    def test_initial_buffer_requires_contiguous_voiced_coverage(self):
        with patch('engine.public_media_url',side_effect=lambda x:x),patch.object(self.e.pool,'submit'):
            r=self.e.start({'video_id':'buffer','prepare_full':True,'duration':60,'sources':['https://test.douyinvod.com/a']})
        j=self.e.find(r['job']);j.update(state='working',coverage=[[0,5]])
        self.assertTrue(self.e.snapshot(r['job'])['progress']['can_play'])
        self.assertFalse(self.e.snapshot(r['job'])['progress']['ready'])
        j['coverage']=[[0,2],[3,10]]
        self.assertFalse(self.e.snapshot(r['job'])['progress']['can_play'])
        j['coverage']=[[0,10]];j['cfg']['speak']=True
        j['lines']=[{'id':'one','start':1,'end':2,'source':'Hello','translation':'Xin chào'}]
        self.assertFalse(self.e.snapshot(r['job'])['progress']['can_play'])
        from engine import digest
        key=digest('edge|v4|'+j['cfg']['voice']+'|Xin chào')
        (self.e.cache/(key+'.mp3')).write_bytes(b'voice')
        self.assertTrue(self.e.snapshot(r['job'])['progress']['can_play'])
        j['metrics']['uncertain_asr_windows']=[[0,5]]
        self.assertFalse(self.e.snapshot(r['job'])['progress']['can_play'])

    def test_full_preparation_queues_voice_beyond_first_six_lines(self):
        import threading
        j={'cfg':{**self.cfg,'speak':True,'preload_all':True},'position':0,'cancel':threading.Event(),
           'lines':[{'translation':'Xin chào '+str(i),'start':i*2,'end':i*2+1} for i in range(12)]}
        with patch.object(self.e,'prefetch_speech',return_value=Mock(done=lambda:False)) as speech:
            self.e.prepare_nearby(j)
            self.assertEqual(speech.call_count,12)

    def test_cached_082_progress_migrates_by_coverage_not_old_window_indices(self):
        from engine import digest
        key=digest('|'.join(['migration',self.cfg['provider'],'cloud',self.cfg['language'],self.cfg['model'],'natural','0.8.2','semantic-words-v3']))
        (self.e.cache/(key+'.json')).write_text(json.dumps({'lines':[],'windows':[0,1],'coverage':[[0,8.2],[8.2,20]],'pending_from':None}))
        with patch('engine.public_media_url',side_effect=lambda x:x),patch.object(self.e.pool,'submit'):
            r=self.e.start({'video_id':'migration','prepare_full':True,'duration':60,'sources':['https://test.douyinvod.com/a']})
        self.assertEqual(self.e.find(r['job'])['windows'],[0,1,2,3])

    def test_collapsed_translation_cannot_become_separate_spoken_words(self):
        from engine import repeated_translation_groups
        words=[{'word':w,'start':i*.2,'end':i*.2+.18} for i,w in enumerate(('皮膚看起來變好了'*11)[:83])]
        collapsed={'lines':[{'from':i,'translation':'đổi'} for i in range(len(words))]}
        with self.assertRaisesRegex(ValueError,'lặp'):aligned_semantic_lines(words,collapsed,0,20)
        collapsed['lines']=[{'from':i,'translation':'và làm giảm sự xuất hiện của nếp nhăn'} for i in range(len(words))]
        with self.assertRaisesRegex(ValueError,'lặp'):aligned_semantic_lines(words,collapsed,0,20)
        legitimate=[{'source':'你好','translation':'Xin chào','start':i,'end':i+.3} for i in range(10)]
        self.assertEqual(repeated_translation_groups(legitimate),[],'genuine repeated source dialogue stays intact')

    def test_corrupt_cached_fragments_are_retranslated_not_silently_removed(self):
        import threading
        from engine import repeated_translation_groups
        bad=[{'id':str(i),'source':w,'translation':'đổi','start':i*.2,'end':i*.2+.18} for i,w in enumerate('皮膚看起來變好了')]
        j={'id':'repair','cfg':self.cfg,'title':'test','video_id':'repair','cancel':threading.Event(),
           'repair_groups':repeated_translation_groups(bad),'lines':[],'windows':[0],'coverage':[[0,2]],'pending_from':None,
           'cache_key':'repair','metrics':{},'revision':0,'position':0,'voice_prepared':False}
        def translate(words,cfg,offset,stop):
            self.assertEqual(''.join(w['word'] for w in words),''.join(x['source'] for x in bad))
            return [{'source':''.join(w['word'] for w in words),'translation':'Da trông tốt hơn rồi.','start':offset,'end':stop}]
        with patch.object(self.e,'translate_words',side_effect=translate):self.e.repair_cached_translation(j)
        self.assertEqual(len(j['lines']),1);self.assertEqual(j['repair_groups'],[])
        self.assertEqual(json.loads((self.e.cache/'repair.json').read_text(encoding='utf-8'))['lines'],j['lines'])

    def test_recognition_survives_engine_restart_without_recognizing_again(self):
        self.cfg['asr']='local'
        recognized={'words':[{'word':'Hello!','start':0,'end':1}],'segments':[]}
        with patch.object(self.e.local_asr,'recognize',return_value=recognized) as recognize,patch.object(self.e,'translate_words',return_value=[]) as translate:
            self.e.groq(b'recognition-cache-fixture',self.cfg,0,2)
            self.assertEqual(recognize.call_count,1)
            self.e.recognition_cache.clear()
            self.e.groq(b'recognition-cache-fixture',self.cfg,0,2)
            self.assertEqual(recognize.call_count,1)
            self.assertEqual(translate.call_count,2,'disk recognition cache must still translate the actual words')
        with patch.object(self.e.local_asr,'recognize',return_value=recognized) as recognize,patch.object(self.e,'translate_words',return_value=[]):
            self.e.groq(b'different-audio',self.cfg,0,2)
            self.assertEqual(recognize.call_count,1,'different audio cannot reuse another transcript')

    def test_voice_batch_starts_before_slow_translation_batch_finishes(self):
        self.cfg['asr']='local';primed=__import__('threading').Event()
        words=[{'word':'hello','start':i*.05,'end':i*.05+.04} for i in range(160)]
        def translate(batch,cfg,offset,stop):
            if batch[0]['start']>0:self.assertTrue(primed.wait(1),'first voice should be queued before waiting for later text')
            return [{'source':'hello','translation':'Xin chào','start':batch[0]['start'],'end':batch[-1]['end'],'complete':True}]
        cfg={**self.cfg,'_prime_speech':lambda lines:primed.set()}
        with patch.object(self.e.local_asr,'recognize',return_value={'words':words,'segments':[]}),patch.object(self.e,'translate_words',side_effect=translate):
            self.assertEqual(len(self.e.groq(b'voice-pipeline-fixture',cfg,0,10)),2)
        self.assertTrue(primed.is_set())

    def test_complete_video_cache_never_opens_media_source(self):
        from engine import digest,VERSION
        key=digest('|'.join(['complete-cache',self.cfg['provider'],'cloud',self.cfg['language'],self.cfg['model'],'natural',VERSION,'semantic-words-v3']))
        (self.e.cache/(key+'.json')).write_text(json.dumps({'lines':[],'windows':[0,1],'coverage':[[0,10]],'pending_from':None}))
        with patch('engine.public_media_url',side_effect=lambda x:x),patch.object(self.e,'source',side_effect=AssertionError('must not fetch cached media')):
            r=self.e.start({'video_id':'complete-cache','prepare_full':True,'duration':10,'sources':['https://test.douyinvod.com/a']})
            deadline=time.monotonic()+2
            while self.e.snapshot(r['job'])['state'] not in ('ready','error') and time.monotonic()<deadline:time.sleep(.01)
            self.assertEqual(self.e.snapshot(r['job'])['state'],'ready')

    def test_corrupt_recognition_cache_falls_back_to_actual_recognition(self):
        from engine import digest
        import hashlib
        self.cfg['asr']='local';raw=b'corrupt-cache-fixture'
        key=hashlib.sha256(raw).hexdigest()+'|zh|local'
        cached=self.e.cache/('asr-v1-'+digest(key)+'.json')
        cached.write_text('{"words":["broken"]}',encoding='utf-8')
        with patch.object(self.e.local_asr,'recognize',return_value={'words':[],'segments':[]}) as recognize:
            self.assertEqual(self.e.groq(raw,self.cfg,0,2),[]);recognize.assert_called_once()
        self.assertTrue(self.e.valid_recognition_cache(json.loads(cached.read_text(encoding='utf-8'))))

    def test_different_short_affirmative_replies_are_allowed_to_repeat(self):
        from engine import repeated_translation_groups
        lines=[{'source':w,'translation':'Vâng.','start':i*.2,'end':i*.2+.18} for i,w in enumerate(['是','对','好']*3)]
        self.assertEqual(repeated_translation_groups(lines),[])

    def test_untranslated_chinese_is_retried_before_any_speech(self):
        def reply(text):
            r=response({'choices':[{'message':{'content':json.dumps({'lines':[{'from':0,'translation':text}]})}}]});r.status_code=200;return r
        words=[{'word':'你好。','start':0,'end':1}]
        with patch('engine.HttpClient.post',side_effect=[reply('你好。'),reply('Xin chào.')]) as post:
            lines=self.e.translate_words(words,self.cfg,0,2)
        self.assertEqual(lines[0]['translation'],'Xin chào.');self.assertEqual(post.call_count,2)
        with patch.object(self.e.speech_pool,'submit') as submit:
            with self.assertRaises(ValueError):self.e.prefetch_speech('Xin chào 你好','vi-VN-NamMinhNeural')
            submit.assert_not_called()

    def test_unchanged_english_and_non_text_are_not_valid_translations(self):
        for text,source in [('This is my home.','This is my home.'),(None,'hello'),('欢迎 John','欢迎')]:
            with self.assertRaises(ValueError):validate_translation(text,source)
        self.assertEqual(validate_translation('John Smith','John Smith'),'John Smith')

    def test_high_no_speech_probability_does_not_erase_confident_dialogue(self):
        segment={'start':0,'end':1,'text':'你好。','no_speech_prob':.95,'avg_logprob':-.2}
        words=[{'word':'你好。','start':.1,'end':.9}]
        self.assertEqual(len(sentence_segments({'segments':[segment],'words':words},0,2)),1)
        self.assertEqual(len(sentence_segments({'segments':[segment]},0,2)),1)
        segment['avg_logprob']=-1.5
        self.assertEqual(sentence_segments({'segments':[segment],'words':words},0,2),[])

    def test_rapid_word_with_equal_timestamps_is_retained(self):
        lines=sentence_segments({'words':[{'word':'你好','start':.1,'end':.1}]},0,2)
        self.assertEqual(lines[0]['source'],'你好');self.assertAlmostEqual(lines[0]['end']-lines[0]['start'],.04)

    def test_long_video_stops_prefetch_until_position_advances(self):
        source=self.media();calls=[]
        def recognize(raw,cfg,start,end):
            calls.append((start,end))
            return []
        with patch('engine.public_media_url',side_effect=lambda x:x),patch.object(self.e,'source',return_value=source),patch.object(self.e,'decode',return_value=b'WAV'),patch.object(self.e,'transcribe',side_effect=recognize):
            r=self.e.start({'video_id':'lookahead','duration':600,'sources':['https://test.douyinvod.com/a']})
            deadline=time.monotonic()+3
            while self.e.snapshot(r['job'])['state']!='buffered' and time.monotonic()<deadline:time.sleep(.01)
            self.assertEqual(calls,[(0,13),(8,43)])
            self.e.seek(r['job'],300)
            while len(calls)<3 and time.monotonic()<deadline:time.sleep(.01)
            self.assertEqual(calls[2],(298,333))
            self.e.cancel(r['job'])
            self.e.pool.shutdown(wait=True,cancel_futures=True)

    def test_explicit_full_preparation_covers_entire_selected_video(self):
        with patch('engine.public_media_url',side_effect=lambda x:x),patch.object(self.e,'source',return_value=self.media()),patch.object(self.e,'decode',return_value=b'WAV'),patch.object(self.e,'transcribe',return_value=[]):
            result=self.e.start({'video_id':'full-selected','position':40,'prepare_full':True,'duration':60,'sources':['https://test.douyinvod.com/a']})
            deadline=time.monotonic()+3
            while self.e.snapshot(result['job'])['state'] not in ('ready','error') and time.monotonic()<deadline:time.sleep(.01)
            s=self.e.snapshot(result['job']);self.assertEqual(s['state'],'ready');self.assertEqual(s['progress']['percent'],100);self.assertTrue(s['progress']['ready']);self.assertEqual(sorted(s['windows']),list(range(12)))
            self.assertFalse(self.cfg.get('preload_all',False),'full preparation is scoped to this job')

if __name__=='__main__':unittest.main(verbosity=2)
