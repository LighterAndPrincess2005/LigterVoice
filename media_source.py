"""Seekable, validated HTTP relay for FFmpeg; media is read on demand."""
import re
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urljoin
import requests


class RemoteMedia:
    def __init__(self, urls, validate, cancelled, metrics, browser=None):
        self.urls = list(urls)
        self.validate = validate
        self.cancelled = cancelled
        self.metrics = metrics
        self.last_error = ''
        self.browser = browser
        self.gate = threading.BoundedSemaphore(4)
        self.guard = threading.Lock()
        self.closed = False
        self.path = '/' + secrets.token_urlsafe(24)
        media = self

        class Relay(BaseHTTPRequestHandler):
            protocol_version = 'HTTP/1.1'

            def log_message(self, *_):
                pass

            def do_HEAD(self):
                self.serve(True)

            def do_GET(self):
                self.serve(False)

            def serve(self, head):
                # Only the decoder holding this random URL can request this one source.
                if self.path != media.path or media.closed or media.cancelled.is_set():
                    self.send_error(404)
                    return
                requested = self.headers.get('Range', '')
                if requested and not re.fullmatch(r'bytes=(?:\d+-\d*|-\d+)', requested):
                    self.send_error(416)
                    return
                if not media.gate.acquire(blocking=False):
                    self.send_error(503)
                    return
                response = None
                try:
                    response = media.open(requested, head)
                    self.send_response(response.status_code)
                    for name in ('Content-Length', 'Content-Range', 'Content-Type', 'Accept-Ranges'):
                        if name in response.headers:
                            self.send_header(name, response.headers[name])
                    self.send_header('Connection', 'close')
                    self.end_headers()
                    self.close_connection = True
                    if not head:
                        for chunk in response.iter_content(64 * 1024):
                            if media.closed or media.cancelled.is_set():
                                break
                            if chunk:
                                with media.guard:
                                    media.metrics['media_bytes'] = media.metrics.get('media_bytes', 0) + len(chunk)
                                self.wfile.write(chunk)
                                self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                    # Normal: FFmpeg closes a range once it has enough packets.
                    pass
                except Exception:
                    media.last_error = 'Không đọc được phần audio từ CDN. Tải lại trang rồi thử lại.'
                    if response is None:
                        self.send_error(502)
                finally:
                    if response is not None:
                        response.close()
                    media.gate.release()

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Relay)
        self.server.daemon_threads = True
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True, name='media-range')
        self.thread.start()
        self.url = f'http://127.0.0.1:{self.server.server_address[1]}{self.path}'

    def __str__(self):
        return self.url

    def open(self, requested, head):
        headers = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://www.douyin.com/', 'Accept-Encoding': 'identity'}
        if requested:
            headers['Range'] = requested
        for initial in list(self.urls):
            url = initial
            for _ in range(6):
                if self.closed or self.cancelled.is_set():
                    raise ValueError('Đã dừng đọc audio.')
                try:
                    self.validate(url)
                    response = self.browser(url,requested,head) if self.browser else requests.request(
                        'HEAD' if head else 'GET', url, headers=headers, stream=True,
                        allow_redirects=False, timeout=(8, 15))
                    if response.status_code in (301, 302, 303, 307, 308):
                        target = urljoin(url, response.headers.get('Location', ''))
                        response.close()
                        url = target
                        continue
                    if response.status_code in (200, 206):
                        if requested and response.status_code == 206 and not response.headers.get('Content-Range'):
                            response.close()
                            break
                        with self.guard:
                            self.metrics['media_requests'] = self.metrics.get('media_requests', 0) + 1
                            self.metrics['range_requests'] = self.metrics.get('range_requests', 0) + bool(requested)
                            if initial in self.urls:
                                self.urls.remove(initial)
                                self.urls.insert(0, initial)
                        return response
                    response.close()
                    break
                except (requests.RequestException, ValueError, OSError):
                    break
        raise ValueError('CDN không trả phần audio cần dùng.')

    def close(self):
        self.closed = True
        self.server.shutdown()
        self.server.server_close()

