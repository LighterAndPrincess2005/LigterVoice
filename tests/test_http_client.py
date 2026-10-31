import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from http_client import HttpClient

class KeepAliveTest(unittest.TestCase):
    def test_connections_reused_per_worker_and_closed(self):
        ports=[]
        class Handler(BaseHTTPRequestHandler):
            protocol_version='HTTP/1.1'
            def do_POST(self):
                self.rfile.read(int(self.headers.get('Content-Length',0)));ports.append(self.client_address[1])
                body=b'{"ok":true}';self.send_response(200);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
            def log_message(self,*a):pass
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start();http=HttpClient()
        try:
            url='http://127.0.0.1:'+str(server.server_port)
            for _ in range(2):self.assertTrue(http.post(url,json={}).json()['ok'])
            worker=threading.Thread(target=lambda:http.post(url,json={}));worker.start();worker.join(3)
            self.assertFalse(worker.is_alive());self.assertEqual(ports[0],ports[1]);self.assertNotEqual(ports[1],ports[2])
            self.assertEqual(len(http.sessions),2)
        finally:http.close();server.shutdown();server.server_close()
        with self.assertRaises(RuntimeError):http.post(url,json={})
