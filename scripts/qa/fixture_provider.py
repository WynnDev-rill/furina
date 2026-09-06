"""Deterministic HTTP/SSE peer for release-APK QA; never packaged in the app."""
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class ProviderFixture:
    def __init__(self, port=8765):
        self.requests = []
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))))
                owner.requests.append(body)
                prompt = body['messages'][-1]['content']
                if 'QA_RATE' in prompt:
                    self.send_response(429)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(b'{"error":{"message":"QA rate limit"}}')
                    return
                if not body.get('stream'):
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(b'{"choices":[{"message":{"content":"OK"}}]}')
                    return
                self.send_response(200)
                self.send_header('Content-Type', 'text/event-stream')
                self.end_headers()
                slow = 'QA_STOP' in prompt or 'QA_RECOVER' in prompt
                prefix = 'Pulih ' if 'QA_RECOVER' in prompt else 'Potongan ' if slow else 'Jawaban uji '
                try:
                    count = 80 if slow else 3
                    for index in range(count):
                        value = prefix + str(index) + '. '
                        payload = json.dumps({'choices': [{'delta': {'content': value}}]})
                        self.wfile.write(('data: ' + payload + '\n\n').encode())
                        self.wfile.flush()
                        time.sleep(.4 if slow else .1)
                    self.wfile.write(b'data: [DONE]\n\n')
                    self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    pass

        self.server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def start(self):
        self.thread.start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()
