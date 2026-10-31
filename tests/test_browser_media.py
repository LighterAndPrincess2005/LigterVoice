import base64
import concurrent.futures
import io
import queue
import tempfile
import threading
import time
import unittest
import wave
from pathlib import Path
from unittest.mock import patch
from browser_media import BrowserMedia, LIMIT
from engine import Engine
from media_source import RemoteMedia


class BrowserRangeTest(unittest.TestCase):
    def test_bounded_range_and_owner_isolation(self):
        broker=BrowserMedia(timeout=1);job={'owner':'tab-7','cancel':threading.Event()}
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future=pool.submit(broker.fetch,job,'https://a.douyinvod.com/a','bytes=200-')
            deadline=time.monotonic()+1
            while not broker.pending and time.monotonic()<deadline:time.sleep(.005)
            self.assertEqual(broker.pull('other')['requests'],[])
            request=broker.pull('tab-7')['requests'][0]
            self.assertEqual(request['range'],f'bytes=200-{200+LIMIT-1}')
            self.assertEqual(broker.pull('tab-7')['requests'],[])
            broker.push({'id':request['id'],'status':206,'headers':{'Content-Range':'bytes 200-202/1000'},'body':base64.b64encode(b'abc').decode()})
            response=future.result(timeout=1)
            self.assertEqual(b''.join(response.iter_content(2)),b'abc');response.close()
        self.assertEqual(broker.pending,{})

    def test_cancel_and_late_result(self):
        broker=BrowserMedia(timeout=1);job={'owner':'tab-7','cancel':threading.Event()}
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future=pool.submit(broker.fetch,job,'https://a.douyinvod.com/a','bytes=0-')
            deadline=time.monotonic()+1
            while not broker.pending and time.monotonic()<deadline:time.sleep(.005)
            request=broker.pull('tab-7')['requests'][0];job['cancel'].set()
            with self.assertRaises(ValueError):future.result(timeout=1)
            self.assertTrue(broker.push({'id':request['id'],'error':'late'})['expired'])
        self.assertEqual(broker.pending,{})

    def test_real_ffmpeg_decodes_browser_ranges(self):
        broker=BrowserMedia(timeout=3);job={'owner':'tab-7','cancel':threading.Event()}
        buffer=io.BytesIO()
        with wave.open(buffer,'wb') as w:
            w.setnchannels(1);w.setsampwidth(2);w.setframerate(16000);w.writeframes(b'\x01\x00'*16000*12)
        payload=buffer.getvalue();stop=threading.Event();requests=[]
        def browser():
            while not stop.wait(.005):
                for request in broker.pull('tab-7')['requests']:
                    requests.append(request);start,end=map(int,request['range'][6:].split('-'));part=payload[start:min(end+1,len(payload))]
                    broker.push({'id':request['id'],'status':206,'headers':{'Content-Range':f'bytes {start}-{start+len(part)-1}/{len(payload)}'},'body':base64.b64encode(part).decode()})
        thread=threading.Thread(target=browser);thread.start()
        with tempfile.TemporaryDirectory() as tmp:
            e=Engine(tmp,lambda:{},queue.Queue())
            relay=RemoteMedia(['https://a.douyinvod.com/a'],lambda url:url,job['cancel'],{},browser=lambda url,r,h:broker.fetch(job,url,r,h))
            try:
                audio=e.decode(relay,5,2,job)
                with wave.open(io.BytesIO(audio)) as w:self.assertAlmostEqual(w.getnframes()/w.getframerate(),2,places=2)
                self.assertTrue(requests)
            finally:relay.close();e.close();stop.set();thread.join(timeout=2)

    def test_prefetch_waits_after_head_and_claim_keeps_same_job(self):
        with tempfile.TemporaryDirectory() as tmp:
            e=Engine(tmp,lambda:{'key':'fake','speak':False},queue.Queue());observed=[]
            def transcribe(raw,cfg,start,end):
                observed.append(start);return [{'start':start+.1,'end':start+1,'source':'你好','translation':'Xin chào'}]
            try:
                with patch('engine.public_media_url',side_effect=lambda url:url),patch.object(e,'source',return_value=Path(tmp)/'fake'),patch.object(e,'decode',return_value=b'WAV'),patch.object(e,'transcribe',side_effect=transcribe):
                    result=e.start({'video_id':'next','owner':'tab-7:next','duration':30,'sources':['https://a.douyinvod.com/a'],'prefetch':True})
                    deadline=time.monotonic()+2
                    while e.snapshot(result['job'])['state']!='buffered' and time.monotonic()<deadline:time.sleep(.01)
                    self.assertEqual(observed,[0]);self.assertEqual(e.snapshot(result['job'])['windows'],[0])
                    promoted=e.claim(result['job'],'tab-7',0)
                    self.assertEqual(promoted['job'],result['job'])
                    deadline=time.monotonic()+2
                    while e.snapshot(result['job'])['state']!='ready' and time.monotonic()<deadline:time.sleep(.01)
                    self.assertEqual(e.snapshot(result['job'])['state'],'ready');self.assertGreater(len(observed),1)
            finally:e.close();e.pool.shutdown(wait=True,cancel_futures=True)


if __name__=='__main__':unittest.main()
