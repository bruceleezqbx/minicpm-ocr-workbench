"""对照实验：同一块内容用不同 Jev 类别打分，验证低分来自类别而非识别错误。

官方 SKILL 明确：category 必须与块的实际类型一致，公式块按 text 送会改变分数含义。
本脚本用同一张裁块、同一段文本，只改 category，观察分数差异。

用法:
    python E:\\OCR\\scripts\\category_probe.py --run <run 目录>
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


def score(base: str, original: Path, render: Path, text: str) -> float | None:
    body = {"items": [{
        "original_image": base64.b64encode(original.read_bytes()).decode(),
        "render_image": base64.b64encode(render.read_bytes()).decode(),
        "ocr_text": text,
    }]}
    req = urllib.request.Request(base.rstrip("/") + "/v1/score", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as resp:
        res = json.load(resp)["results"][0]
    return res.get("prob_1")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--score-url", default="http://127.0.0.1:18501")
    ap.add_argument("--work", default=r"E:\OCR\work\jev_probe")
    args = ap.parse_args()

    run = Path(args.run)
    work = Path(args.work)
    work.mkdir(parents=True, exist_ok=True)

    for page_file in sorted((run / "results_json").glob("*.json")):
        page = json.loads(page_file.read_text(encoding="utf-8"))
        image_id = page.get("image_id", page_file.stem)
        crop_dir = run / "runtime" / "intermediate" / "crops" / image_id
        for blk in page.get("crop_blocks", []):
            if blk.get("label") not in {"display_formula", "inline_formula"}:
                continue
            content = blk.get("content") or ""
            img = crop_dir / (blk.get("crop_filename") or "")
            if not img.is_file():
                continue
            print(f"\n=== {img.name} (label={blk['label']}) ===")
            print(f"    文本: {content[:80]}")
            for cat in ("formula", "text"):
                cand = Candidate(case_id=f"{img.stem}_{cat}", image_path=str(img),
                                 text=content, category=cat)
                res = render_candidates([cand], work_dir=work / f"{img.stem}_{cat}")[0]
                if not res.ok:
                    print(f"    [{cat}] 渲染失败: {res.reason} {res.detail}")
                    continue
                p = score(args.score_url, img, Path(res.render_image_path), content)
                print(f"    [{cat}] prob_1 = {p:.5f}" if p is not None else f"    [{cat}] 打分失败")
    return 0


if __name__ == "__main__":
    sys.exit(main())
