"""Bounded media ranges fetched by the authorized browser tab, without cookies in Python."""
import base64
import io
import re
import secrets
import threading
import time
import requests

LIMIT = 1024 * 1024


class BrowserMedia:
    def __init__(self, timeout=12):
        self.timeout = timeout
        self.guard = threading.Lock()
        self.pending = {}

    def fetch(self, job, url, requested, head=False):
        match = re.fullmatch(r'bytes=(\d+)-(\d*)', requested or 'bytes=0-')
        if match:
            start = int(match[1]); end = min(start+LIMIT-1, int(match[2]) if match[2] else start+LIMIT-1)
            requested = f'bytes={start}-{end}'
        elif re.fullmatch(r'bytes=-\d+', requested):
            requested = f'bytes=-{min(LIMIT,int(requested[7:]))}'
        else:
            raise ValueError('Khoảng audio không hợp lệ.')
        key = secrets.token_urlsafe(24)
        record = {'owner':job['owner'], 'event':threading.Event(), 'result':None,
                  'command':{'id':key,'url':url,'range':requested}, 'sent':False}
        with self.guard:
            if len(self.pending)>=12:raise ValueError('Đang chờ trình duyệt đọc audio.')
            self.pending[key] = record
        try:
            deadline = time.monotonic()+self.timeout
            while not record['event'].wait(.1):
                if job['cancel'].is_set():raise ValueError('Đã đổi video.')
                if time.monotonic()>deadline:raise ValueError('Trình duyệt chưa trả phần audio.')
            data = record['result']
            if data.get('error'):raise ValueError(str(data['error'])[:250])
            body = base64.b64decode(data.get('body',''),validate=True)
            if not body or len(body)>LIMIT:raise ValueError('Phần audio không hợp lệ.')
            response = requests.Response(); response.status_code = int(data.get('status',0))
            if response.status_code not in (200,206):raise ValueError('Trình duyệt chưa đọc được audio CDN.')
            response.headers.update({k:str(v)[:200] for k,v in data.get('headers',{}).items()
                                     if k in ('Content-Length','Content-Range','Content-Type','Accept-Ranges')})
            response.headers['Content-Length'] = str(len(body))
            response.raw = io.BytesIO(body)
            return response
        finally:
            with self.guard:self.pending.pop(key,None)

    def pull(self, owner):
        with self.guard:
            records=[r for r in self.pending.values() if r['owner']==owner and not r['sent']][:4]
            for r in records:r['sent']=True
            return {'requests':[dict(r['command']) for r in records]}

    def push(self, data):
        body=data.get('body','')
        if not isinstance(body,str) or len(body)>((LIMIT+2)//3)*4:raise ValueError('Phần audio vượt giới hạn.')
        with self.guard:
            record=self.pending.get(str(data.get('id','')))
            if record is None:return {'ok':True,'expired':True}
            record['result']=data;record['event'].set()
        return {'ok':True}
