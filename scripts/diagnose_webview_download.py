#!/usr/bin/env python3
"""诊断：pywebview(WebView2) 里的下载能不能落盘。

背景：桌面壳用 Edge WebView2，而 pywebview 没有接 CoreWebView2.DownloadStarting。
WebView2 在没有下载处理器时会静默取消下载，所以工作台里点"下载"毫无反应。
这个脚本用两种常见方式各试一次，把结论直接打出来：

    A. blob URL + <a download> 点击      —— 前端 saveImageParseExport 用的就是这套
    B. 跳转到带 Content-Disposition 的 URL —— 服务端直出附件的标准做法

用法：
    E:\\OCR\\.desktop\\Scripts\\python.exe E:\\OCR\\scripts\\diagnose_webview_download.py

退出码：0 = 至少有一种方式能落盘；1 = 都落不了盘（说明桌面壳必须走 JS 桥）
"""
import http.server
import os
import sys
import threading
import time
from pathlib import Path

import webview

PORT = 18997
DOWNLOADS = Path(os.path.expanduser("~")) / "Downloads"


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = b"hello-desktop-download"
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Disposition", 'attachment; filename="diag_server.txt"')
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def snapshot():
    if not DOWNLOADS.exists():
        return set()
    return {p.name for p in DOWNLOADS.iterdir()}


srv = http.server.HTTPServer(("127.0.0.1", PORT), Handler)
threading.Thread(target=srv.serve_forever, daemon=True).start()

before = snapshot()
print(f"[diag] 起始 Downloads 文件数: {len(before)}", flush=True)

JS_BLOB = """
(() => {
  const b = new Blob(['hello-blob'], {type: 'text/plain'});
  const u = URL.createObjectURL(b);
  const a = document.createElement('a');
  a.href = u;
  a.download = 'diag_blob.txt';
  document.body.appendChild(a);
  a.click();
  a.remove();
  return 'clicked';
})()
"""


def on_loaded():
    try:
        print(f"[diag] A blob+anchor -> {window.evaluate_js(JS_BLOB)}", flush=True)
    except Exception as exc:  # noqa: BLE001
        print(f"[diag] A 失败: {exc}", flush=True)
    time.sleep(3)
    try:
        window.load_url(f"http://127.0.0.1:{PORT}/x")
    except Exception as exc:  # noqa: BLE001
        print(f"[diag] B load_url 失败: {exc}", flush=True)
    time.sleep(4)
    window.destroy()


window = webview.create_window("下载诊断", f"http://127.0.0.1:{PORT}/x", width=800, height=600)
window.events.loaded += on_loaded
webview.start()
time.sleep(1)

new = sorted(snapshot() - before)
print(f"[diag] 最终新增文件: {new}", flush=True)
ok_a = any("diag_blob" in n for n in new)
ok_b = any("diag_server" in n for n in new)
print(f"[diag] A(blob 链接)          {'能落盘' if ok_a else '不能落盘'}", flush=True)
print(f"[diag] B(Content-Disposition) {'能落盘' if ok_b else '不能落盘'}", flush=True)
if not (ok_a or ok_b):
    print("[diag] 结论: 这个 WebView2 里没有浏览器下载机制，桌面壳必须走 pywebview 的 JS 桥。", flush=True)
    sys.exit(1)
print("[diag] 结论: 浏览器下载机制可用，走官方那套 blob 下载即可。", flush=True)
sys.exit(0)
