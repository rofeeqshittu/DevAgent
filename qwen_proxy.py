import os
import threading
import urllib.request
import urllib.error
from http.server import HTTPServer, BaseHTTPRequestHandler

TARGET_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode"

class ProxyHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)
        
        req = urllib.request.Request(TARGET_URL + self.path, data=body)
        api_key = os.getenv("QWEN_API_KEY")
        if api_key:
            req.add_header('Authorization', f'Bearer {api_key}')
        req.add_header('Content-Type', 'application/json')
        
        try:
            with urllib.request.urlopen(req) as response:
                self.send_response(response.getcode())
                for key, val in response.getheaders():
                    self.send_header(key, val)
                self.end_headers()
                self.wfile.write(response.read())
        except urllib.error.HTTPError as e:
            self.send_response(e.code)
            self.end_headers()
            self.wfile.write(e.read())
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(str(e).encode('utf-8'))

    def log_message(self, format, *args):
        pass

def start_proxy(port=0):
    httpd = HTTPServer(('127.0.0.1', port), ProxyHTTPRequestHandler)
    actual_port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd, actual_port
