import io
import queue
import re
import sys
import tempfile
import threading
import time
import unittest
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import requests

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from engine import Engine
from media_source import RemoteMedia


class RangeMediaTest(unittest.TestCase):
    def setUp(self):
        # Ten minutes of PCM. Seeking near its end must not download the whole file.
        out=io.BytesIO()
        with wave.open(out,'wb') as f:
            f.setnchannels(1);f.setsampwidth(2);f.setframerate(16000)
            f.writeframes(b'\0\0'*16000*600)
        self.content=out.getvalue()
        content=self.content
        self.requests=[]
        seen=self.requests
        class Origin(BaseHTTPRequestHandler):
            def log_message(self,*_):pass
            def do_GET(self):
                requested=self.headers.get('Range','')
                seen.append(requested)
                match=re.fullmatch(r'bytes=(\d+)-(\d*)',requested)
                start=int(match[1]) if match else 0
                end=min(len(content)-1,int(match[2]) if match and match[2] else len(content)-1)
                self.send_response(206 if match else 200)
                self.send_header('Content-Length',str(end-start+1))
                self.send_header('Content-Type','audio/wav')
                self.send_header('Accept-Ranges','bytes')
                if match:self.send_header('Content-Range',f'bytes {start}-{end}/{len(content)}')
                self.end_headers()
                try:
                    for at in range(start,end+1,16384):
                        self.wfile.write(content[at:min(at+16384,end+1)]);self.wfile.flush()
                        time.sleep(.001)
                except OSError:pass
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Origin)
        self.server.daemon_threads=True
        threading.Thread(target=self.server.serve_forever,daemon=True).start()
        self.cancel=threading.Event();self.metrics={}
        self.media=RemoteMedia([f'http://127.0.0.1:{self.server.server_address[1]}/fixture'],lambda u:u,self.cancel,self.metrics)

    def tearDown(self):
        self.cancel.set();self.media.close();self.server.shutdown();self.server.server_close()

    def test_range_forwarding_and_private_path(self):
        r=requests.get(str(self.media),headers={'Range':'bytes=100-120'},timeout=3)
        self.assertEqual(r.status_code,206)
        self.assertEqual(r.content,self.content[100:121])
        self.assertEqual(r.headers['Content-Range'],f'bytes 100-120/{len(self.content)}')
        self.assertEqual(self.requests,['bytes=100-120'])
        self.assertEqual(requests.get(str(self.media)+'/unknown',timeout=3).status_code,404)
        self.assertEqual(requests.get(str(self.media),headers={'Range':'bytes=0-1,4-5'},timeout=3).status_code,416)

    def test_ffmpeg_seeks_by_range_without_full_download(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine=Engine(tmp,lambda:{},queue.Queue())
            try:
                raw=engine.decode(self.media,550,2,{'cancel':self.cancel})
                with wave.open(io.BytesIO(raw)) as f:
                    self.assertEqual(f.getframerate(),16000)
                    self.assertEqual(len(f.readframes(40000)),64000)
                self.assertTrue(any(int(re.match(r'bytes=(\d+)-',r)[1])>16_000_000 for r in self.requests if r))
                self.assertLess(self.metrics['media_bytes'],len(self.content)//4)
            finally:
                engine.close()

    def test_cancel_rejects_further_reads(self):
        self.cancel.set()
        self.assertEqual(requests.get(str(self.media),timeout=3).status_code,404)


if __name__=='__main__':unittest.main()
