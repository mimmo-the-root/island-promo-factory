"""Tiny mock of the ComfyUI HTTP API (enough for qwen_run.py / upscale.py). No GPU needed."""
import io
import json
import re
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from PIL import Image, ImageDraw


class _Handler(BaseHTTPRequestHandler):
    last_prompt_text = ""

    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, (bytes, bytearray)) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path.startswith("/system_stats"):
            return self._send(200, {"system": {"mock": True}})
        if self.path.startswith("/object_info/UpscaleModelLoader"):
            return self._send(200, {"UpscaleModelLoader": {"input": {"required": {"model_name": [[]]}}}})
        if self.path.startswith("/history/"):
            pid = self.path.rsplit("/", 1)[1]
            return self._send(200, {pid: {"status": {"completed": True, "status_str": "success", "messages": []},
                                          "outputs": {"195": {"images": [{"filename": "mock.png", "subfolder": "", "type": "output"}]}}}})
        if self.path.startswith("/view"):
            vertical = "VERTICAL" in _Handler.last_prompt_text.upper()
            size = (880, 1184) if vertical else (1392, 752)
            im = Image.new("RGB", size, (30, 40, 70))
            d = ImageDraw.Draw(im)
            d.rectangle((size[0] * 0.1, size[1] * 0.2, size[0] * 0.3, size[1] * 0.9), fill=(200, 120, 60))
            buf = io.BytesIO()
            im.save(buf, "PNG")
            return self._send(200, buf.getvalue(), "image/png")
        self._send(404, {"error": "not found"})

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(n)
        if self.path.startswith("/upload/image"):
            m = re.search(rb'filename="([^"]+)"', body)
            return self._send(200, {"name": m.group(1).decode() if m else "upload.png", "subfolder": "", "type": "input"})
        if self.path.startswith("/prompt"):
            wf = json.loads(body).get("prompt", {})
            _Handler.last_prompt_text = str(wf.get("170:151", {}).get("inputs", {}).get("prompt", ""))
            return self._send(200, {"prompt_id": "mock-prompt", "node_errors": {}})
        self._send(404, {"error": "not found"})


def start(port=0):
    server = HTTPServer(("127.0.0.1", port), _Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, server.server_address[1]
