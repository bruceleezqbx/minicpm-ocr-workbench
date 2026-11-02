#!/usr/bin/env python3
# 本机改造：本文件在上游 OpenBMB/MiniCPM-OCR 版本基础上被修改。
# Apache-2.0 §4(b) 要求被修改的文件声明改动；完整改动清单见 E:\OCR\CHANGES.md
"""用 Pandoc 把解析结果导出成 Word，公式是 Word 原生公式（OMML，可继续编辑）。

为什么不用官方前端那个导出：它的 docx 导出是纯前端做的，公式分支明确"保留 LaTeX 源码为纯文本"，
所以 Word 里看到的是 \\frac{...} 而不是排好版的公式。这里走另一条路：

    Markdown -> HTML 表格转 pipe 表格 -> pandoc -> docx

pandoc 自带 LaTeX 数学到 OMML 的转换器，**不需要安装 LaTeX 发行版**。
"""
from __future__ import annotations

import html
import os
import re
import shutil
import subprocess
import tempfile
from html.parser import HTMLParser
from pathlib import Path
from typing import List

#: pandoc 可执行文件；优先用 PATH 上的，其次用本机安装位置与本机的便携版
PANDOC_CANDIDATES = (
    os.environ.get("OCR_PANDOC", ""),
    r"E:\OCR\sources\pandoc\pandoc-3.13\pandoc.exe",
    r"C:\Program Files\Pandoc\pandoc.exe",
    r"C:\Users\{user}\AppData\Local\Pandoc\pandoc.exe",
)


def find_pandoc() -> str | None:
    for cand in PANDOC_CANDIDATES:
        if cand and Path(cand).is_file():
            return cand
    found = shutil.which("pandoc")
    return found


class _TableParser(HTMLParser):
    """把 HTML 表格拆成行 -> 单元格纯文本。"""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: List[List[str]] = []
        self._row: List[str] | None = None
        self._cell: List[str] | None = None
        self._in_table = False

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self._in_table = True
        elif tag == "tr" and self._in_table:
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []

    def handle_endtag(self, tag):
        if tag == "table" and self._in_table:
            self._in_table = False
        elif tag == "tr" and self._row is not None:
            self.rows.append(self._row)
            self._row = None
        elif tag in ("td", "th") and self._cell is not None and self._row is not None:
            text = " ".join("".join(self._cell).split())
            self._row.append(text)
            self._cell = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)


def _cell(text: str) -> str:
    return text.replace("|", r"\|").strip()


def html_table_to_pipe(table_html: str) -> str:
    """HTML 表格 -> pandoc 能读的 pipe 表格。"""
    parser = _TableParser()
    parser.feed(table_html)
    rows = [r for r in parser.rows if any(c for c in r)]
    if not rows:
        return table_html
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    lines = ["| " + " | ".join(_cell(c) for c in rows[0]) + " |"]
    lines.append("| " + " | ".join("---" for _ in range(width)) + " |")
    for row in rows[1:]:
        lines.append("| " + " | ".join(_cell(c) for c in row) + " |")
    return "\n".join(lines)


def convert_html_tables(markdown: str) -> str:
    """把正文里的 HTML 表格换成 pipe 表格（pandoc 的 markdown reader 不认 HTML 表格）。"""
    pattern = re.compile(r"<table\b[^>]*>.*?</table>", re.S | re.I)

    def repl(match: "re.Match[str]") -> str:
        return html_table_to_pipe(match.group(0))

    return pattern.sub(repl, markdown)


def strip_images(markdown: str) -> str:
    """去掉图片引用。远程图片会让 pandoc 抓取失败，整份导出一起挂掉。"""
    markdown = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", markdown)
    markdown = re.sub(r"<img\b[^>]*>", "", markdown, flags=re.I)
    return markdown


#: 公式：$$..$$ 与 $..$；表格：pipe table
_READER = "markdown+tex_math_dollars+pipe_tables+raw_html+footnotes+yaml_metadata_block"


def markdown_to_docx_bytes(markdown: str) -> bytes:
    """Markdown -> docx 字节流。优先保留公式；失败时退化为无公式、无图片的版本。"""
    pandoc = find_pandoc()
    if not pandoc:
        raise RuntimeError("找不到 pandoc，请先安装（winget install JohnMacFarlane.Pandoc）")

    prepared = convert_html_tables(markdown)
    with tempfile.TemporaryDirectory(prefix="word_export_") as tmp:
        work = Path(tmp)
        attempts = [
            ("full", prepared),
            ("no_images", strip_images(prepared)),
            ("plain", strip_images(convert_html_tables(markdown))),
        ]
        errors = []
        for name, text in attempts:
            src = work / f"{name}.md"
            out = work / f"{name}.docx"
            src.write_text(text, encoding="utf-8")
            proc = subprocess.run(
                [pandoc, "-f", _READER, "-t", "docx", "--resource-path", str(work), "-o", str(out), str(src)],
                capture_output=True, text=True, timeout=300,
            )
            if proc.returncode == 0 and out.is_file() and out.stat().st_size > 0:
                return out.read_bytes()
            errors.append(f"{name}: {proc.stderr.strip()[-300:]}")
        raise RuntimeError("pandoc 导出失败：" + " | ".join(errors))


def html_table_stats(markdown: str) -> dict:
    """统计正文里的表格与公式，供自检使用。"""
    return {
        "html_tables": len(re.findall(r"<table\b", markdown, re.I)),
        "display_math": len(re.findall(r"\$\$", markdown)),
    }
