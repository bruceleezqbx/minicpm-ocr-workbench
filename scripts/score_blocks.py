"""读判闭环：对 1.0 解析出的每个块做 Jev 质检，产出带分数的报告。

流程：
  1.0 结果(results_json) + 版面裁块(crops)  ->  按类别渲染 OCR 文本 ->  Jev 打分  ->  报告

类别映射只认 Jev 训练过的三类（text / formula / table）；seal、figure 等其它版面类型
没有对应的训练类别，按官方说法硬塞进 text 会让分数失真，因此跳过并在报告里列出。

阈值：Jev 官方不给阈值，分数只适合在同一次输入集合内比较。这里用 --threshold 给一个
可调的提示线，仅用于报告里的"建议复核"标注，不是官方口径。

用法:
    python E:\\OCR\\scripts\\score_blocks.py --run <runs 目录> [--threshold 0.5]
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

#: Jev 训练过的三类
FORMULA_LABELS = {"display_formula", "inline_formula", "formula", "isolated_formula"}
TABLE_LABELS = {"table", "table_caption", "table_footnote"}
TEXT_LABELS = {
    "text", "paragraph_title", "figure_title", "figure_caption", "chart_title",
    "doc_title", "section_header", "header", "footer", "page_number",
    "reference", "footnote", "list", "seal_text", "abandon",
}


def jev_category(label: str) -> str | None:
    """把版面标签映射到 Jev 的类别；无法映射返回 None（该块跳过打分）。"""
    l = (label or "").strip().lower()
    if l in FORMULA_LABELS:
        return "formula"
    if l in TABLE_LABELS:
        return "table"
    if l in TEXT_LABELS:
        return "text"
    return None


def post_score(url: str, items: list[dict]) -> list[dict]:
    req = urllib.request.Request(
        url,
        data=json.dumps({"items": items}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=900) as resp:
        return json.load(resp)["results"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, help="SDK 的一次 run 目录")
    ap.add_argument("--score-url", default="http://127.0.0.1:18501")
    ap.add_argument("--threshold", type=float, default=0.5)
    ap.add_argument("--out", default="")
    ap.add_argument("--work", default=r"E:\OCR\work\jev_loop")
    args = ap.parse_args()

    run = Path(args.run)
    results_dir = run / "results_json"
    pages = sorted(results_dir.glob("*.json"))
    if not pages:
        print(f"没有 results_json: {results_dir}")
        return 2

    work = Path(args.work)
    work.mkdir(parents=True, exist_ok=True)
    out_md = Path(args.out) if args.out else work / "jev_report.md"
    out_json = out_md.with_suffix(".json")

    candidates: list[Candidate] = []
    meta: dict[str, dict] = {}
    skipped: list[dict] = []

    for page_file in pages:
        page = json.loads(page_file.read_text(encoding="utf-8"))
        image_id = page.get("image_id", page_file.stem)
        crop_dir = run / "runtime" / "intermediate" / "crops" / image_id
        for blk in page.get("crop_blocks", []):
            label = blk.get("label", "")
            content = blk.get("content") or ""
            fname = blk.get("crop_filename") or ""
            img = crop_dir / fname
            cat = jev_category(label)
            if cat is None:
                skipped.append({"label": label, "reason": "Jev 无此版面类别", "text": content[:60]})
                continue
            if not content.strip():
                skipped.append({"label": label, "reason": "无文本", "text": ""})
                continue
            if not img.is_file():
                skipped.append({"label": label, "reason": f"缺裁块 {fname}", "text": content[:60]})
                continue
            cid = f"{image_id}_{fname}"
            candidates.append(Candidate(case_id=cid, image_path=str(img), text=content, category=cat))
            meta[cid] = {"label": label, "category": cat, "content": content, "image": str(img)}

    if not candidates:
        print("没有可打分的块")
        for s in skipped:
            print(f"  跳过 [{s['label']}] {s['reason']}")
        return 2

    print(f"待打分 {len(candidates)} 块，跳过 {len(skipped)} 块")

    # 1) 渲染
    print("渲染中（playwright + KaTeX）...")
    rendered = render_candidates(candidates, work_dir=work / "render", browser_concurrency=2)
    render_results = {r.case_id: r for r in rendered}
    printable = [c for c in candidates if render_results.get(c.case_id, None) and render_results[c.case_id].ok]
    print(f"  渲染成功 {len(printable)}/{len(candidates)}")

    # 2) 打分
    items = []
    for c in printable:
        r = render_results[c.case_id]
        items.append({
            "original_image": base64.b64encode(Path(meta[c.case_id]["image"]).read_bytes()).decode(),
            "render_image": base64.b64encode(Path(r.render_image_path).read_bytes()).decode(),
            "ocr_text": meta[c.case_id]["content"],
        })
    print(f"打分中（{len(items)} 块）...")
    results = post_score(f"{args.score_url}/v1/score", items)

    # 3) 报告
    rows = []
    for c, res in zip(printable, results):
        m = meta[c.case_id]
        prob = res.get("prob_1")
        rows.append({
            "case_id": c.case_id,
            "label": m["label"],
            "category": m["category"],
            "prob_1": prob,
            "error": res.get("error"),
            "text": m["content"],
        })

    lines = [
        "# MiniCPM-OCR Jev 质检报告",
        "",
        f"- run: `{run}`",
        f"- 打分块数: {len(rows)}  跳过: {len(skipped)}",
        f"- 阈值(仅报告用, 非官方口径): {args.threshold}",
        "",
        "| # | 版面类型 | Jev类别 | prob_1 | 判定 | 文本摘要 |",
        "|---|---|---|---|---|---|",
    ]
    for i, r in enumerate(rows, 1):
        if r["prob_1"] is None:
            verdict, prob = "打分失败", "-"
        else:
            verdict = "通过" if r["prob_1"] >= args.threshold else "建议复核"
            prob = f"{r['prob_1']:.5f}"
        summary = r["text"].replace("\n", " ").replace("|", "\\|")
        if len(summary) > 60:
            summary = summary[:60] + "…"
        lines.append(f"| {i} | {r['label']} | {r['category']} | {prob} | {verdict} | {summary} |")

    if skipped:
        lines += ["", "## 跳过的块", "", "| 版面类型 | 原因 | 文本摘要 |", "|---|---|---|"]
        for s in skipped:
            summary = (s["text"] or "").replace("\n", " ").replace("|", "\\|")[:60]
            lines.append(f"| {s['label']} | {s['reason']} | {summary} |")

    scored = [r["prob_1"] for r in rows if r["prob_1"] is not None]
    if scored:
        low = sum(1 for p in scored if p < args.threshold)
        lines += ["", f"合计 {len(scored)} 块计分，{low} 块低于阈值 {args.threshold}。"]

    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    out_json.write_text(json.dumps({"run": str(run), "rows": rows, "skipped": skipped},
                                   ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"报告: {out_md}")
    print(f"明细: {out_json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
