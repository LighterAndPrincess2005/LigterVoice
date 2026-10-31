import io
import json
from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import patch
import requests
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app

class TransportTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=app.ThreadingHTTPServer(('127.0.0.1',0),app.Handler)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()
        cls.url='http://127.0.0.1:'+str(cls.server.server_port)
        cls.headers={'Authorization':'Bearer '+app.settings['token']}
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close()
    def test_authorization_and_origin(self):
        self.assertEqual(requests.post(self.url+'/status').status_code,401)
        self.assertEqual(requests.post(self.url+'/status',headers=self.headers).status_code,200)
        self.assertEqual(requests.post(self.url+'/status',headers={**self.headers,'Origin':'https://evil.example'}).status_code,403)
    def test_bad_json_not_crash(self):
        r=requests.post(self.url+'/jobs/start',headers=self.headers,data='[]')
        self.assertEqual(r.status_code,400)
    def test_old_continuous_client_cannot_allocate_unrequested_jobs(self):
        with patch.object(app.engine,'start') as start:
            r=requests.post(self.url+'/jobs/start',headers=self.headers,json={'owner':'tab-7','video_id':'old-client'})
        self.assertEqual(r.status_code,409);start.assert_not_called()
    def test_job_router_and_speech_pending(self):
        with patch.object(app.engine,'start',return_value={'job':'test-job'}):
            r=requests.post(self.url+'/jobs/start',headers=self.headers,json={'video_id':'test'})
        self.assertEqual(r.json(),{'job':'test-job'})
        with patch.object(app.engine,'speech',return_value={'pending':True}):
            r=requests.post(self.url+'/speech',headers=self.headers,json={'job':'test-job','line_id':'hi'})
        self.assertEqual(r.json(),{'pending':True})
    def test_malformed_audio(self):
        r=requests.post(self.url+'/audio',headers=self.headers,data=b'invalid'*20)
        self.assertEqual(r.status_code,400)
    def test_browser_media_and_warm_claim_routes(self):
        with patch.object(app.engine.browser_media,'pull',side_effect=[{'requests':[{'id':'range-test'}]},{'requests':[]}]):
            r=requests.post(self.url+'/media/pull',headers=self.headers,json={'owner':'tab-7'})
        self.assertEqual(r.json()['requests'],[{'id':'range-test'}])
        with patch.object(app.engine.browser_media,'push',return_value={'ok':True}) as push:
            r=requests.post(self.url+'/media/push',headers=self.headers,json={'id':'range-test','body':'YWJj','status':206})
        self.assertEqual(r.status_code,200);self.assertEqual(push.call_args.args[0]['body'],'YWJj')
        with patch.object(app.engine,'claim',return_value={'job':'warm-job','warm':True}):
            r=requests.post(self.url+'/jobs/claim',headers=self.headers,json={'job':'warm-job','owner':'tab-7','position':.2})
        self.assertTrue(r.json()['warm'])
    def test_playback_report_tracks_actual_independent_audio(self):
        data={'protocol':7,'job':'test','position':10,'audio_time':2.5,'audio_volume':1,'audio_muted':False,'source_paused':False,'speaking':True}
        r=requests.post(self.url+'/playback/report',headers=self.headers,json=data)
        self.assertEqual(r.status_code,200)
        status=requests.post(self.url+'/status',headers=self.headers).json()
        self.assertEqual(status['playback']['audio_time'],2.5);self.assertTrue(status['playback']['speaking'])
        self.assertEqual(status['playback_mode'],'smooth')

if __name__=='__main__':unittest.main()
