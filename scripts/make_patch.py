#!/usr/bin/env python3
"""生成本机改造的标准补丁（a/ b/ 相对路径），并验证它能干净地打到上游基线上。

用法：
    E:\\OCR\\.minicpm-ocr\\Scripts\\python.exe E:\\OCR\\scripts\\make_patch.py
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

BASE = Path(r"E:\OCR\work\_baseline\MiniCPM-OCR-main")
CUR = Path(r"E:\OCR\sources\MiniCPM-OCR-main")
STAGE = Path(r"E:\OCR\work\_patchstage")
OUT = Path(r"E:\OCR\upstream-local.patch")

MODIFIED = [
    r"webdemo\backend\document_jobs.py",
    r"webdemo\backend\model_manager.py",
    r"webdemo\backend\page_fleet.py",
    r"webdemo\backend\server.py",
    r"webdemo\frontend\src\api\map\request.ts",
    r"webdemo\frontend\src\i18n\messages\playground.ts",
    r"webdemo\frontend\src\pages\playground\components\experiences\ImageParseDocumentWorkspace.tsx",
    r"webdemo\frontend\src\pages\playground\components\experiences\ImageParseDownloadMenu.tsx",
    r"webdemo\frontend\src\pages\playground\components\experiences\ImageParseExperience.tsx",
    r"webdemo\frontend\src\pages\playground\components\experiences\ImageParseResultPane.tsx",
    r"webdemo\frontend\src\pages\playground\components\experiences\ImageParseUploadSurface.tsx",
    r"webdemo\frontend\src\pages\playground\hooks\useImageParseDownload.ts",
    r"webdemo\frontend\src\pages\playground\hooks\useImageParseRegeneration.ts",
    r"webdemo\frontend\src\pages\playground\hooks\useImageParseResultState.ts",
    r"webdemo\frontend\src\pages\playground\utils\imageParseExport.ts",
    r"webdemo\frontend\src\pages\playground\utils\imageParseFeatureFlags.ts",
    r"webdemo\frontend\src\pages\playground\utils\imageParseRegenerationRequest.ts",
    r"webdemo\frontend\vite.config.ts",
]
ADDED = [
    r"webdemo\backend\jev_quality.py",
    r"webdemo\backend\jev_regenerate.py",
    r"webdemo\backend\word_export.py",
]
GITIGNORE = ".gitignore"


def stage() -> tuple[Path, Path]:
    """把改动前后的同名文件摆到 a/ b/ 两棵树下。

    a/ = 上游基线版本（新增文件在 a/ 里不存在）
    b/ = 本机当前版本
    """
    if STAGE.exists():
        shutil.rmtree(STAGE)
    a, b = STAGE / "a", STAGE / "b"

    def put(root: Path, rel: str, src: Path) -> None:
        dst = root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

    for rel in MODIFIED:
        base_src = BASE / rel
        cur_src = CUR / rel
        if not base_src.is_file() or not cur_src.is_file():
            print(f"跳过（缺文件）：{rel}")
            continue
        put(a, rel, base_src)
        put(b, rel, cur_src)

    for rel in ADDED + [GITIGNORE]:
        cur_src = CUR / rel
        if not cur_src.is_file():
            print(f"跳过（缺文件）：{rel}")
            continue
        put(b, rel, cur_src)

    return a, b


def make_patch(a: Path, b: Path) -> str:
    # 必须关掉 autocrlf：全局 git 开了它，diff 出来的上下文会带 CRLF，
    # 而上游 tarball 的文件是 LF，git apply 就匹配不上了。
    proc = subprocess.run(
        [
            "git", "-c", "core.autocrlf=false", "-c", "core.safecrlf=false",
            "--no-pager", "diff", "--no-index", "--binary", "--no-color", "--", "a", "b",
        ],
        cwd=str(STAGE),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    text = proc.stdout
    # git 的 --no-index 目录对比会写成 "a/a/xxx" / "b/b/xxx"（新增文件是 "a/b/xxx"）
    text = text.replace("b/b/", "b/")
    text = text.replace("a/a/", "a/").replace("a/b/", "a/")
    text = re.sub(r"^--- a/a/", "--- a/", text, flags=re.M)
    text = re.sub(r"^\+\+\+ b/b/", "+++ b/", text, flags=re.M)
    return text


def verify(patch_text: str) -> bool:
    """在一份全新的上游基线副本上试打这个补丁。"""
    tmp = Path(r"E:\OCR\work\_patchverify")
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    target = tmp / "repo"
    shutil.copytree(BASE, target, ignore=shutil.ignore_patterns(
        "node_modules", "dist", "__pycache__", "*.pyc"
    ))
    patch_file = tmp / "local.patch"
    # 必须写字节：Python 文本模式在 Windows 上会把 \n 翻成 \r\n，
    # 补丁行尾一旦变成 CRLF，git apply 就匹配不上 LF 的基线文件。
    patch_file.write_bytes(patch_text.encode("utf-8"))
    proc = subprocess.run(
        [
            "git", "-c", "core.autocrlf=false", "-c", "core.safecrlf=false",
            "apply", "--check", "--verbose", str(patch_file),
        ],
        cwd=str(target),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    ok = proc.returncode == 0
    print(f"git apply --check -> {'通过' if ok else '失败'}")
    if not ok:
        print(proc.stdout[-1500:])
        print(proc.stderr[-1500:])
    shutil.rmtree(tmp, ignore_errors=True)
    return ok


def main() -> int:
    a, b = stage()
    patch_text = make_patch(a, b)
    # 同样写字节，保证补丁文件本身是 LF
    OUT.write_bytes(patch_text.encode("utf-8"))
    entries = len(re.findall(r"^diff --git ", patch_text, flags=re.M))
    print(f"补丁已生成：{OUT}（{OUT.stat().st_size} 字节，{entries} 个文件条目）")
    if not verify(patch_text):
        print("补丁验证未通过")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
