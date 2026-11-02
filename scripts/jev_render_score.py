"""Jev 逐块质检 worker：由 webdemo 后端以子进程方式调用。

输入一个 JSON 作业文件，输出一段 JSON 到 stdout：
  {"crops_dir": ..., "work_dir": ..., "score_url": "http://127.0.0.1:18501",
   "blocks": [{"order": 0, "label": "text", "crop_filename": "000_text.png", "content": "..."}]}
输出：
  [{"order": 0, "prob_1": 0.997, "category": "text", "render": "渲染图路径"}, ...]

为什么单独一个进程：渲染要 playwright + KaTeX，装在 .jev-render 这个独立 venv 里；
webdemo 后端跑在 .minicpm-ocr venv 里，两者不能共用解释器。

用法:
    E:\\OCR\\.jev-render\\Scripts\\python.exe E:\\OCR\\scripts\\jev_render_score.py --job job.json
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
import urllib.request
from pathlib import Path

SDK = Path(r"E:\OCR\sources\MiniCPM-OCR-main\scripts\minicpm-ocr-jev")
sys.path.insert(0, str(SDK))

from rm_render import Candidate, render_candidates  # noqa: E402

#: Jev 训练过的三类；其它版面类型没有对应类别，硬塞进 text 会让分数失真
FORMULA_LABELS = {"display_formula", "inline_formula", "formula", "isolated_formula"}
TABLE_LABELS = {"table", "table_caption", "table_footnote"}
TEXT_LABELS = {
    "text", "paragraph_title", "figure_title", "figure_caption", "chart_title",
    "doc_title", "section_header", "header", "footer", "page_number",
    "reference", "footnote", "list", "seal_text", "abandon",
}


def jev_category(label: str) -> str | None:
    l = (label or "").strip().lower()
    if l in FORMULA_LABELS:
        return "formula"
    if l in TABLE_LABELS:
        return "table"
    if l in TEXT_LABELS:
        return "text"
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--job", required=True, type=Path)
    args = ap.parse_args()

    job = json.loads(args.job.read_text(encoding="utf-8"))
    crops_dir = Path(job["crops_dir"])
    work_dir = Path(job["work_dir"])
    score_url = job.get("score_url", "http://127.0.0.1:18501").rstrip("/")
    work_dir.mkdir(parents=True, exist_ok=True)

    candidates = []
    meta = {}
    skipped = []
    for blk in job.get("blocks", []):
        label = blk.get("label", "")
        content = blk.get("content") or ""
        fname = blk.get("crop_filename") or ""
        cat = jev_category(label)
        if cat is None:
            skipped.append({"order": blk.get("order"), "reason": "no_jev_category"})
            continue
        if not content.strip():
            skipped.append({"order": blk.get("order"), "reason": "empty_text"})
            continue
        img = crops_dir / fname
        if not img.is_file():
            skipped.append({"order": blk.get("order"), "reason": "missing_crop"})
            continue
        cid = f"{blk.get('order', 0)}_{cat}"
        candidates.append(Candidate(case_id=cid, image_path=str(img), text=content, category=cat))
        meta[cid] = dict(blk, _img=str(img), _category=cat)

    if not candidates:
        json.dump({"results": [], "skipped": skipped}, sys.stdout, ensure_ascii=False)
        return 0

    # 1) 渲染：playwright + KaTeX，渲染图是 Jev 的第二张输入
    rendered = render_candidates(candidates, work_dir=work_dir, browser_concurrency=2)
    by_id = {r.case_id: r for r in rendered}

    # 2) 打分：一次请求送全部块
    items = []
    order_of = []
    for c in candidates:
        r = by_id.get(c.case_id)
        if r is None or not r.ok:
            skipped.append({"order": meta[c.case_id].get("order"), "reason": "render_failed"})
            continue
        items.append({
            "original_image": base64.b64encode(Path(meta[c.case_id]["_img"]).read_bytes()).decode(),
            "render_image": base64.b64encode(Path(r.render_image_path).read_bytes()).decode(),
            "ocr_text": meta[c.case_id]["content"],
        })
        order_of.append((c, r))

    results = []
    if items:
        body = json.dumps({"items": items}).encode()
        req = urllib.request.Request(
            score_url + "/v1/score", data=body,
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=1800) as resp:
            scores = json.load(resp)["results"]
        for (c, r), sc in zip(order_of, scores):
            results.append({
                "order": meta[c.case_id].get("order"),
                "prob_1": sc.get("prob_1"),
                "error": sc.get("error"),
                "category": meta[c.case_id].get("_category"),
                "render": r.render_image_path,
            })

    json.dump({"results": results, "skipped": skipped}, sys.stdout, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
