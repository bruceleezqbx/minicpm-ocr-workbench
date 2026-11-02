#!/usr/bin/env python3
"""给本机改过的上游文件加上 Apache-2.0 §4(b) 要求的改动声明。

§4(b)：Redistribution ... "(b) You must cause any modified files to carry
prominent notices stating that You changed the files."

幂等：已经带声明的文件会跳过。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(r"E:\OCR\sources\MiniCPM-OCR-main")

PY_MARK = (
    "# 本机改造：本文件在上游 OpenBMB/MiniCPM-OCR 版本基础上被修改。\n"
    "# Apache-2.0 §4(b) 要求被修改的文件声明改动；完整改动清单见 E:\\OCR\\CHANGES.md\n"
)
TS_MARK = (
    "/**\n"
    " * 本机改造：本文件在上游 OpenBMB/MiniCPM-OCR 版本基础上被修改。\n"
    " * Apache-2.0 §4(b) 要求被修改的文件声明改动；完整改动清单见 E:\\OCR\\CHANGES.md\n"
    " */\n"
)

# 修改过的上游文件（对照上游原始 tarball 用哈希比对得出）
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

# 本机新增的上游目录内的文件
ADDED = [
    r"webdemo\backend\jev_quality.py",
    r"webdemo\backend\jev_regenerate.py",
    r"webdemo\backend\word_export.py",
]

NEEDLE = "本机改造"


def add_python_notice(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    if NEEDLE in text.split("\n\n")[0] or text.startswith(NEEDLE):
        return False
    lines = text.split("\n")
    insert_at = 0
    if lines and lines[0].startswith("#!"):
        insert_at = 1
    lines.insert(insert_at, PY_MARK.rstrip("\n"))
    path.write_text("\n".join(lines), encoding="utf-8")
    return True


def add_ts_notice(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    head = "\n".join(text.split("\n")[:6])
    if NEEDLE in head:
        return False
    path.write_text(TS_MARK + text, encoding="utf-8")
    return True


def main() -> int:
    changed = 0
    for rel in MODIFIED + ADDED:
        path = ROOT / rel
        if not path.is_file():
            print(f"缺失: {rel}")
            continue
        ok = add_python_notice(path) if path.suffix == ".py" else add_ts_notice(path)
        if ok:
            changed += 1
            print(f"已加声明: {rel}")
    print(f"\n共处理 {changed} 个文件")
    return 0


if __name__ == "__main__":
    sys.exit(main())
