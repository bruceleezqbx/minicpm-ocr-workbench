#!/usr/bin/env python3
# 本机改造：本文件在上游 OpenBMB/MiniCPM-OCR 版本基础上被修改。
# Apache-2.0 §4(b) 要求被修改的文件声明改动；完整改动清单见 E:\OCR\CHANGES.md
"""单块重识别 + 重新质检（本机扩展）。

官方前端的「一键重识别」是打云端 L2 接口（要 API Key + 页面凭证），本地没有那条路。
这里给本机补一条等价通道：

    POST /api/jev/regenerate
      {"image": "<页面图 base64>", "bbox": [x1,y1,x2,y2], "label": "display_formula"}
    -> {"markdown": "重新识别出的块内容", "prob_1": 0.87, "confidence": 0.87, "old": "..."}

流程：裁块 -> 用 1.0 重新识别（走本机 Ollama）-> 渲染 -> Jev 重新打分。
"""
from __future__ import annotations

import base64
import binascii
import io
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict

from PIL import Image

#: Jev 训练过的三类；其它版面类型没有对应类别，硬塞进 text 会让分数失真
FORMULA_LABELS = {"display_formula", "inline_formula", "formula", "isolated_formula"}
TABLE_LABELS = {"table", "table_caption", "table_footnote"}
TEXT_LABELS = {
    "text", "paragraph_title", "figure_title", "figure_caption", "chart_title",
    "doc_title", "section_header", "header", "footer", "page_number",
    "reference", "footnote", "list", "seal_text", "abandon",
}

JEV_PYTHON = os.environ.get("OCRWEB_JEV_PYTHON", r"E:\OCR\.jev-render\Scripts\python.exe")
JEV_WORKER = os.environ.get("OCRWEB_JEV_WORKER", r"E:\OCR\scripts\jev_render_score.py")
JEV_SCORE_URL = os.environ.get("OCRWEB_JEV_SCORE_URL", "http://127.0.0.1:18501")


def jev_category(label: str):
    l = (label or "").strip().lower()
    if l in FORMULA_LABELS:
        return "formula"
    if l in TABLE_LABELS:
        return "table"
    if l in TEXT_LABELS:
        return "text"
    return None


def _decode_image(data_url: str) -> bytes:
    raw = data_url.split(",", 1)[1] if data_url.startswith("data:") else data_url
    return base64.b64decode(raw, validate=False)


def recognize_crop(crop: Image.Image, label: str) -> str:
    """用本机 1.0 重新识别这一块。"""
    import server  # 复用后端已有的识别客户端（指向本机 Ollama）
    from minicpmvocr.prompts import DEFAULT_PROMPT_MAP, get_element_cfg

    elem = get_element_cfg(DEFAULT_PROMPT_MAP, label)
    if not elem:
        elem = get_element_cfg(DEFAULT_PROMPT_MAP, "text")
    service = getattr(server, "OCR_SVC", None)
    if service is None:
        service = server.OcrService()
    result = service.recognize(
        crop,
        prompt=elem["prompt"],
        max_new_tokens=int(elem.get("max_new_tokens", 4096)),
    )
    if isinstance(result, dict):
        return str(result.get("text") or "")
    return str(result or "")


def score_crop(crop: Image.Image, text: str, category: str) -> float | None:
    """渲染这块文本并让 Jev 打分。"""
    import subprocess

    with tempfile.TemporaryDirectory(prefix="jev_regen_") as tmp:
        work = Path(tmp)
        crop_path = work / "block.png"
        crop.save(crop_path)
        job = {
            "crops_dir": str(work),
            "work_dir": str(work / "render"),
            "score_url": JEV_SCORE_URL,
            "blocks": [{
                "order": 0,
                "label": "text" if category == "formula" else category,
                "crop_filename": "block.png",
                "content": text,
            }],
        }
        job_file = work / "job.json"
        job_file.write_text(json.dumps(job, ensure_ascii=False), encoding="utf-8")
        proc = subprocess.run(
            [JEV_PYTHON, JEV_WORKER, "--job", str(job_file)],
            capture_output=True, text=True, timeout=1200,
        )
        if proc.returncode != 0:
            print(f"[jev] 重新打分失败: {proc.stderr[-400:]}", flush=True)
            return None
        try:
            out = json.loads(proc.stdout)
        except Exception:
            return None
        for item in out.get("results", []):
            if item.get("prob_1") is not None:
                return float(item["prob_1"])
    return None


def regenerate_block(payload: Dict[str, Any]) -> Dict[str, Any]:
    image_b64 = payload.get("image")
    bbox = payload.get("bbox")
    label = str(payload.get("label") or "text")
    if not image_b64 or not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
        raise ValueError("需要 image 与 bbox")
    raw = _decode_image(str(image_b64))
    with Image.open(io.BytesIO(raw)) as page:
        page = page.convert("RGB")
        values = [float(v) for v in bbox]
        # 归一化坐标(x,y,w,h ∈ [0,1]) 按页面实际像素换算；像素坐标直接用。
        if max(values) <= 1.5:
            x = values[0] * page.width
            y = values[1] * page.height
            w = values[2] * page.width
            h = values[3] * page.height
        else:
            x, y, w, h = values
        crop = page.crop((
            max(0, int(round(x))),
            max(0, int(round(y))),
            min(page.width, int(round(x + w))),
            min(page.height, int(round(y + h))),
        ))
    text = recognize_crop(crop, label)
    category = jev_category(label)
    prob = score_crop(crop, text, category or "text") if category else None
    return {
        "markdown": text,
        "text": text,
        "prob_1": prob,
        "confidence": prob,
        "category": category,
    }
