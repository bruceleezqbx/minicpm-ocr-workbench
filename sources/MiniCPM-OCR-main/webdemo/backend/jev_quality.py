#!/usr/bin/env python3
# 本机改造：本文件在上游 OpenBMB/MiniCPM-OCR 版本基础上被修改。
# Apache-2.0 §4(b) 要求被修改的文件声明改动；完整改动清单见 E:\OCR\CHANGES.md
"""Jev 逐块质检（本机扩展）。

官方前端按 block.score 做三件事：低分块标红、复核面板列���、"一键重识别"。
云端版本这个分数来自 TTS 自评分（多轮重识别时选最优候选）；
本地没有那套服务，这里用 MiniCPM-OCR Jev 的一致性分数补上：

    prob_1 = 1.0  ->  该块 OCR 文本与原图一致
    prob_1 = 0.0  ->  文本读起来通顺，但和原图对不上

两者语义方向一致（越高越可信），所以可以直接填进同一个字段。

渲染需要 playwright + KaTeX，装在独立 venv 里，因此这一步用子进程调用 worker。
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List

JEV_ENABLED = os.environ.get("OCRWEB_JEV", "0").strip().lower() not in ("", "0", "false", "no")
JEV_PYTHON = os.environ.get("OCRWEB_JEV_PYTHON", r"E:\OCR\.jev-render\Scripts\python.exe")
JEV_WORKER = os.environ.get("OCRWEB_JEV_WORKER", r"E:\OCR\scripts\jev_render_score.py")
JEV_SCORE_URL = os.environ.get("OCRWEB_JEV_SCORE_URL", "http://127.0.0.1:18501")

#: Jev 训练过的三类；其它版面类型没有对应类别，硬塞进 text 会让分数失真
FORMULA_LABELS = {"display_formula", "inline_formula", "formula", "isolated_formula"}
TABLE_LABELS = {"table", "table_caption", "table_footnote"}
TEXT_LABELS = {
    "text", "paragraph_title", "figure_title", "figure_caption", "chart_title",
    "doc_title", "section_header", "header", "footer", "page_number",
    "reference", "footnote", "list", "seal_text", "abandon",
}


def jev_category(label: str):
    """把版面标签映射到 Jev 类别；无法映射返回 None（该块不参与打分）。"""
    l = (label or "").strip().lower()
    if l in FORMULA_LABELS:
        return "formula"
    if l in TABLE_LABELS:
        return "table"
    if l in TEXT_LABELS:
        return "text"
    return None


def _worker(job: Dict, work_dir: Path) -> Dict:
    job_file = work_dir / "jev_job.json"
    job_file.write_text(json.dumps(job, ensure_ascii=False), encoding="utf-8")
    proc = subprocess.run(
        [JEV_PYTHON, JEV_WORKER, "--job", str(job_file)],
        capture_output=True, text=True, timeout=2400,
    )
    if proc.returncode != 0:
        print(f"[jev] worker 退出码 {proc.returncode}: {proc.stderr[-500:]}", flush=True)
        return {"results": [], "skipped": []}
    try:
        return json.loads(proc.stdout)
    except Exception as exc:
        print(f"[jev] worker 输出解析失败: {exc}", flush=True)
        return {"results": [], "skipped": []}


def score_page(job_dir: Path, stem: str, result: Dict) -> int:
    """给一页的 crop_blocks 打分，把 prob_1 写进每个块的 jev_score。返回打分块数。"""
    if not JEV_ENABLED:
        return 0
    crops_dir = job_dir / "runtime" / "intermediate" / "crops" / stem
    if not crops_dir.is_dir():
        print(f"[jev] {stem}: 没有裁块目录，跳过质检", flush=True)
        return 0
    blocks: List[Dict] = []
    for blk in result.get("crop_blocks") or []:
        label = blk.get("label", "")
        content = blk.get("content") or ""
        fname = blk.get("crop_filename") or ""
        if jev_category(label) is None or not content.strip():
            continue
        if not (crops_dir / fname).is_file():
            continue
        blocks.append({
            "order": blk.get("order"),
            "label": label,
            "crop_filename": fname,
            "content": content,
        })
    if not blocks:
        return 0
    with tempfile.TemporaryDirectory(prefix="jev_") as tmp:
        out = _worker({
            "crops_dir": str(crops_dir),
            "work_dir": tmp,
            "score_url": JEV_SCORE_URL,
            "blocks": blocks,
        }, Path(tmp))
    by_order = {item.get("order"): item.get("prob_1") for item in out.get("results", [])}
    scored = 0
    for blk in result.get("crop_blocks") or []:
        prob = by_order.get(blk.get("order"))
        if prob is None:
            continue
        blk["jev_score"] = float(prob)
        scored += 1
    print(f"[jev] {stem}: 已打分 {scored}/{len(blocks)} 块", flush=True)
    return scored


def score_job(job_dir: Path) -> int:
    """给一个 job 目录下所有页打分，并把分数写回 results_json。"""
    if not JEV_ENABLED:
        return 0
    layouts_dir = job_dir / "runtime" / "intermediate" / "layouts"
    results_dir = job_dir / "results_json"
    if not layouts_dir.is_dir():
        return 0
    total = 0
    for layout_path in sorted(layouts_dir.glob("*.json")):
        result_path = results_dir / f"{layout_path.stem}.json"
        if not result_path.is_file():
            continue
        try:
            result = json.loads(result_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        scored = score_page(job_dir, layout_path.stem, result)
        if scored:
            result_path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
            total += scored
    return total
