"""Reuse TLS connections per worker without sharing mutable sessions across threads."""
import threading
import requests


class HttpClient:
    def __init__(self):
        self.local=threading.local();self.lock=threading.Lock();self.sessions=[];self.closed=False

    def post(self,url,**kwargs):
        with self.lock:
            if self.closed:raise RuntimeError('HTTP client is closed')
            session=getattr(self.local,'session',None)
            if session is None:
                session=requests.Session()
                adapter=requests.adapters.HTTPAdapter(pool_connections=2,pool_maxsize=2,max_retries=0)
                session.mount('https://',adapter)
                self.local.session=session;self.sessions.append(session)
        return session.post(url,**kwargs)

    def close(self):
        with self.lock:
            self.closed=True;sessions=self.sessions;self.sessions=[]
        for session in sessions:session.close()
