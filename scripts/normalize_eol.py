#!/usr/bin/env python3
"""把本机改过的上游文件行尾统一回 LF（与上游 tarball 一致）。

上游仓库用 LF；本机编辑工具把整个文件重写成了 CRLF，
后果是 diff 凭空膨胀 10 倍、以后合并上游逐行冲突。
这里只改行尾，不动任何其它字节。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(r"E:\OCR\sources\MiniCPM-OCR-main")

TARGETS = [
    r"webdemo\backend\document_jobs.py",
    r"webdemo\backend\model_manager.py",
    r"webdemo\backend\page_fleet.py",
    r"webdemo\backend\server.py",
    r"webdemo\backend\jev_quality.py",
    r"webdemo\backend\jev_regenerate.py",
    r"webdemo\backend\word_export.py",
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
    r".gitignore",
]


def normalize(path: Path) -> tuple[bool, int]:
    raw = path.read_bytes()
    if b"\r\n" not in raw:
        return False, 0
    fixed = raw.replace(b"\r\n", b"\n")
    path.write_bytes(fixed)
    return True, raw.count(b"\r\n")


def main() -> int:
    changed = 0
    for rel in TARGETS:
        path = ROOT / rel
        if not path.is_file():
            print(f"缺失: {rel}")
            continue
        ok, n = normalize(path)
        if ok:
            changed += 1
            print(f"CRLF -> LF ({n} 行): {rel}")
    print(f"\n共规范化 {changed} 个文件")
    return 0


if __name__ == "__main__":
    sys.exit(main())
