#!/usr/bin/env python3
"""MiniCPM-OCR 读判工作台 · 桌面壳总控

一次双击干完这些事：

  1. 清理上次残留：占端口的旧进程、Ollama 加载失败留下的僵尸 llama-server
  2. 拉起后端服务：1.0 识别(Ollama) / Jev 判别引擎 / Jev 打分 / Web 后端
  3. 逐个探活，全绿之后开一个 Edge WebView2 窗口加载工作台
  4. 关窗口 -> 只停掉这次自己拉起来的服务（之前就在跑的保留）

前端是生产构建产物，由 Web 后端自己托管，所以桌面模式**不需要 Vite dev server**，
进程数比开发模式少一个，窗口打开也更快。

用法：
    E:\\OCR\\.desktop\\Scripts\\python.exe E:\\OCR\\scripts\\desktop_app.py
    E:\\OCR\\.desktop\\Scripts\\python.exe E:\\OCR\\scripts\\desktop_app.py --dev      # 额外起 Vite，从 5173 进
    E:\\OCR\\.desktop\\Scripts\\python.exe E:\\OCR\\scripts\\desktop_app.py --serve-only  # 只起服务不开窗
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

ROOT = Path(r"E:\OCR")
SCRIPTS = ROOT / "scripts"
LOGS = ROOT / "logs"
JEV_ENGINE_DIR = ROOT / "sources" / "llama-b12032"

APP_URL = "http://127.0.0.1:8966/playground/document-parse"
DEV_URL = "http://127.0.0.1:5173/playground/document-parse"

PWSH = "pwsh"


def log(msg: str) -> None:
    print(f"[desktop] {msg}", flush=True)


@dataclass
class Service:
    """一个后端服务：怎么探活、怎么拉起、多久算超时。"""

    name: str
    port: int
    health: str
    script: str
    args: list[str] = field(default_factory=list)
    timeout: int = 120
    proc: subprocess.Popen | None = None
    started_by_us: bool = False


SERVICES: list[Service] = [
    Service("1.0 识别服务 (Ollama)", 18499, "/api/version", "start-ollama.ps1", ["-Mode", "gpu"], timeout=120),
    Service("Jev 判别引擎", 18498, "/health", "start-jev-engine.ps1", ["-Ngl", "0"], timeout=240),
    Service("Jev 打分服务", 18501, "/healthz", "start-jev-score.ps1", [], timeout=120),
    Service("Web 后端（含前端静态托管）", 8966, "/health", "start-webdemo-backend.ps1", [], timeout=150),
]


# ===================================================================
# 残留清理
# ===================================================================

def _ps(script: str) -> str:
    """跑一段 PowerShell，返回 stdout。"""
    proc = subprocess.run(
        [PWSH, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=90,
    )
    return proc.stdout or ""


def _kill_tree(pid: int) -> None:
    """连子进程一起杀（taskkill /T），只杀 PowerShell 父进程会留下孙进程。"""
    subprocess.run(
        ["taskkill", "/PID", str(pid), "/T", "/F"],
        capture_output=True,
        text=True,
        timeout=60,
    )


def pids_listening_on(ports: list[int]) -> list[int]:
    """找出占着这些端口的进程 PID。"""
    if not ports:
        return []
    joined = ",".join(str(p) for p in ports)
    out = _ps(
        "$ErrorActionPreference='SilentlyContinue';"
        f"Get-NetTCPConnection -State Listen -LocalPort {joined} | "
        "Select-Object -ExpandProperty OwningProcess -Unique"
    )
    pids: list[int] = []
    for line in out.splitlines():
        line = line.strip()
        if line.isdigit():
            pid = int(line)
            if pid not in pids:
                pids.append(pid)
    return pids


def zombie_llama_pids() -> list[int]:
    """本机 llama.cpp 引擎目录下、但没在监听端口的僵尸 llama-server。

    Ollama 加载模型失败时会残留一堆 llama-server.exe，工作集 0MB 但仍挂着。
    只认 llama-b12032 目录（Ollama 自己的 runner 在别的目录，不动它）。
    """
    out = _ps(
        "$ErrorActionPreference='SilentlyContinue';"
        f"Get-CimInstance Win32_Process -Filter \"Name='llama-server.exe'\" | "
        f"Where-Object {{ $_.ExecutablePath -like '{JEV_ENGINE_DIR}\\*' }} | "
        "Select-Object -ExpandProperty ProcessId"
    )
    pids: list[int] = []
    for line in out.splitlines():
        line = line.strip()
        if line.isdigit():
            pids.append(int(line))
    return pids


def cleanup_stale(ports: list[int]) -> None:
    """清掉占端口的旧进程和僵尸引擎。

    注意：这里只按「端口」和「可执行文件路径」判断，
    不能拿命令行里的字符串去匹配——那会连本进程自己一起匹配上然后把自己杀了。
    """
    me = os.getpid()
    pids = [p for p in pids_listening_on(ports) if p != me]
    for pid in pids:
        log(f"清理占端口的旧进程 PID {pid}")
        _kill_tree(pid)
    if pids:
        time.sleep(2)

    zombies = [p for p in zombie_llama_pids() if p != me]
    for pid in zombies:
        log(f"清理僵尸 llama-server PID {pid}")
        _kill_tree(pid)
    if zombies:
        time.sleep(1)


# ===================================================================
# 服务拉起与探活
# ===================================================================

def is_healthy(svc: Service) -> bool:
    url = f"http://127.0.0.1:{svc.port}{svc.health}"
    try:
        with urllib.request.urlopen(url, timeout=4) as resp:
            return 200 <= resp.status < 300
    except Exception:  # noqa: BLE001
        return False


def start_service(svc: Service) -> None:
    script = SCRIPTS / svc.script
    if not script.is_file():
        raise FileNotFoundError(f"缺少启动脚本：{script}")
    LOGS.mkdir(parents=True, exist_ok=True)
    cmd = [PWSH, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), *svc.args]
    log(f"启动 {svc.name} ...")
    svc.proc = subprocess.Popen(
        cmd,
        cwd=str(SCRIPTS),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    svc.started_by_us = True


def ensure_service(svc: Service) -> bool:
    """服务已在跑就直接复用，否则拉起来再等健康。"""
    if is_healthy(svc):
        log(f"{svc.name} 已在运行（复用）")
        svc.started_by_us = False
        return True
    start_service(svc)
    deadline = time.time() + svc.timeout
    while time.time() < deadline:
        if svc.proc is not None and svc.proc.poll() is not None:
            log(f"{svc.name} 启动脚本已退出（码 {svc.proc.returncode}）")
            return False
        if is_healthy(svc):
            log(f"{svc.name} 就绪  http://127.0.0.1:{svc.port}{svc.health}")
            return True
        time.sleep(2)
    log(f"{svc.name} {svc.timeout}s 内没就绪")
    return False


def stop_services(services: list[Service]) -> None:
    """只停这次自己拉起来的。"""
    for svc in reversed(services):
        if not svc.started_by_us or svc.proc is None:
            continue
        log(f"停止 {svc.name}")
        _kill_tree(svc.proc.pid)
    time.sleep(1)


# ===================================================================
# 启动页
# ===================================================================

BOOT_HTML = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<title>MiniCPM-OCR 读判工作台</title>
<style>
  * { box-sizing: border-box; }
  body {
    margin: 0; height: 100vh; display: flex; align-items: center; justify-content: center;
    background: radial-gradient(1200px 600px at 50% -10%, #1e293b 0%, #0f172a 55%, #020617 100%);
    color: #e2e8f0;
    font: 14px/1.6 "Segoe UI", "Microsoft YaHei", system-ui, sans-serif;
  }
  .card { width: 520px; padding: 36px 40px; }
  h1 { font-size: 21px; font-weight: 600; margin: 0 0 4px; letter-spacing: .5px; }
  .sub { color: #64748b; font-size: 12px; margin-bottom: 26px; }
  .row { display: flex; align-items: center; gap: 10px; padding: 7px 0; }
  .dot { width: 9px; height: 9px; border-radius: 50%; background: #334155; flex: none; }
  .dot.run { background: #38bdf8; animation: pulse 1s infinite; }
  .dot.ok { background: #34d399; }
  .dot.err { background: #f87171; }
  .name { flex: none; width: 210px; color: #cbd5e1; }
  .msg { color: #64748b; font-size: 12px; }
  .err-msg { color: #f87171; font-size: 12px; }
  .bar { height: 3px; background: #1e293b; border-radius: 3px; margin-top: 24px; overflow: hidden; }
  .bar > i { display: block; height: 100%; width: 0; background: linear-gradient(90deg,#38bdf8,#34d399); transition: width .4s; }
  .foot { margin-top: 14px; color: #475569; font-size: 11px; }
  @keyframes pulse { 0%,100% { opacity: 1 } 50% { opacity: .25 } }
</style>
</head>
<body>
  <div class="card">
    <h1>MiniCPM-OCR 读判工作台</h1>
    <div class="sub">正在启动本机服务，请稍候</div>
    <div id="list"></div>
    <div class="bar"><i id="bar"></i></div>
    <div class="foot" id="foot">全部就绪后会自动进入工作台</div>
  </div>
<script>
  const items = {};
  const list = document.getElementById('list');
  function add(id, name) {
    const row = document.createElement('div');
    row.className = 'row';
    row.innerHTML = '<span class="dot"></span><span class="name"></span><span class="msg"></span>';
    row.querySelector('.name').textContent = name;
    list.appendChild(row);
    items[id] = row;
  }
  window.__setStatus = function (id, state, msg) {
    const row = items[id];
    if (!row) return;
    row.querySelector('.dot').className = 'dot ' + state;
    const target = row.querySelector(state === 'err' ? '.err-msg' : '.msg');
    if (target) target.textContent = msg || '';
  };
  window.__setProgress = function (done, total) {
    document.getElementById('bar').style.width = Math.round(done / total * 100) + '%';
  };
  window.__setFoot = function (text) {
    document.getElementById('foot').textContent = text;
  };
</script>
</body>
</html>
"""


def open_window(services: list[Service], app_url: str, selftest: bool = False) -> int:
    """开窗口；服务就绪后切到工作台。"""
    import webview  # 延迟导入，--serve-only 时不需要 GUI 依赖

    window = webview.create_window(
        "MiniCPM-OCR 读判工作台",
        html=BOOT_HTML,
        width=1440,
        height=920,
        min_size=(1024, 680),
        background_color="#020617",
    )

    def bootstrap() -> None:
        total = len(services)
        for index, svc in enumerate(services):
            try:
                window.evaluate_js(f"add('{svc.port}', '{svc.name}')")
            except Exception:  # noqa: BLE001
                pass
            try:
                window.evaluate_js(
                    f"__setStatus('{svc.port}', 'run', '启动中...')"
                )
            except Exception:  # noqa: BLE001
                pass
            ok = ensure_service(svc)
            try:
                if ok:
                    window.evaluate_js(
                        f"__setStatus('{svc.port}', 'ok', '就绪 :{svc.port}')"
                    )
                else:
                    window.evaluate_js(
                        f"__setStatus('{svc.port}', 'err', '启动失败，看 E:\\OCR\\logs')"
                    )
            except Exception:  # noqa: BLE001
                pass
            try:
                window.evaluate_js(f"__setProgress({index + 1}, {total})")
            except Exception:  # noqa: BLE001
                pass
            if not ok:
                try:
                    window.evaluate_js(
                        "__setFoot('有服务没起来，详情看 E:\\OCR\\logs，窗口可以关掉')"
                    )
                except Exception:  # noqa: BLE001
                    pass
                return

        log("全部就绪，打开工作台")
        try:
            window.evaluate_js("__setFoot('正在进入工作台...')")
            window.load_url(app_url)
        except Exception as exc:  # noqa: BLE001
            log(f"打开工作台失败：{exc}")
            return

        if not selftest:
            return

        # 自检：等前端真的渲染出来，再读页面状态
        deadline = time.time() + 90
        probe = (
            "JSON.stringify({"
            " title: document.title,"
            " href: location.href,"
            " root: !!document.querySelector('#root'),"
            " kids: document.querySelector('#root') ? document.querySelector('#root').children.length : 0,"
            " upload: !!document.querySelector('input[type=file]'),"
            " text: (document.body.innerText || '').slice(0, 160)"
            "})"
        )
        while time.time() < deadline:
            time.sleep(3)
            try:
                raw = window.evaluate_js(probe)
            except Exception as exc:  # noqa: BLE001
                log(f"自检读取失败（可能还在跳转）：{exc}")
                continue
            if not raw:
                continue
            try:
                import json

                info = json.loads(raw)
            except Exception:  # noqa: BLE001
                log(f"自检返回无法解析：{raw!r}")
                continue
            log(f"自检 title={info.get('title')!r} href={info.get('href')!r}")
            log(f"自检 root_children={info.get('kids')} file_input={info.get('upload')}")
            log(f"自检 页面文字：{(info.get('text') or '').strip()[:140]!r}")
            ok = bool(info.get("kids")) and bool(info.get("upload"))
            log(f"自检结果：{'通过' if ok else '未通过（页面可能没渲染完）'}")
            break
        else:
            log("自检超时：90s 内没读到页面状态")

        time.sleep(2)
        try:
            window.destroy()
        except Exception:  # noqa: BLE001
            pass

    webview.start(bootstrap)
    return 0


# ===================================================================
# 入口
# ===================================================================

def main() -> int:
    parser = argparse.ArgumentParser(description="MiniCPM-OCR 桌面壳")
    parser.add_argument("--dev", action="store_true", help="额外起 Vite dev server，从 5173 进")
    parser.add_argument("--serve-only", action="store_true", help="只起服务不开窗口")
    parser.add_argument("--keep", action="store_true", help="退出时不停止服务")
    parser.add_argument(
        "--selftest",
        action="store_true",
        help="开窗后自检页面渲染，读到状态就关窗（用于无人值守验证）",
    )
    args = parser.parse_args()

    services = list(SERVICES)
    if args.dev:
        services.append(
            Service("Web 前端 (Vite dev)", 5173, "/", "start-webdemo-frontend.ps1", [], timeout=120)
        )

    ports = [s.port for s in services]
    log("清理上次残留 ...")
    cleanup_stale(ports)

    try:
        if args.serve_only:
            for svc in services:
                ensure_service(svc)
            log("全部服务已启动（--serve-only，按 Ctrl+C 退出）")
            while True:
                time.sleep(5)
        else:
            open_window(services, DEV_URL if args.dev else APP_URL, selftest=args.selftest)
    except KeyboardInterrupt:
        log("收到 Ctrl+C")
    finally:
        if not args.keep:
            stop_services(services)
        else:
            log("--keep：保留服务运行")
    return 0


if __name__ == "__main__":
    sys.exit(main())
