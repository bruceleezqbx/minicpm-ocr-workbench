"""渲染保真度检查：在本机渲染官方样例的候选文本，与随包发布的 reference_render.png 对照。

官方 SKILL 的 7.2 验证用的是随包参考渲染图；真正跑闭环时渲染图是我们自己生成的，
所以这里先量一下本机渲染栈与参考渲染的差距（尺寸一致率 + 像素差异率），
好知道"本机分数"与"官方公布值"之间有多少是字体/行距带来的。

用法:
    python E:\\OCR\\scripts\\render_check.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

SDK = Path(r"E:\OCR\sources\MiniCPM-OCR-main\scripts\minicpm-ocr-jev")
sys.path.insert(0, str(SDK))

from PIL import Image, ImageChops  # noqa: E402
from rm_render import Candidate, render_candidates  # noqa: E402

EXAMPLES = SDK / "examples"


def pixel_diff(a: Path, b: Path) -> tuple[tuple[int, int], float]:
    ia = Image.open(a).convert("RGB")
    ib = Image.open(b).convert("RGB")
    same_size = ia.size == ib.size
    if not same_size:
        return (ia.size, ib.size), float("nan")
    diff = ImageChops.difference(ia, ib).convert("L")
    hist = diff.histogram()
    total = sum(hist)
    changed = sum(hist[16:])  # 16/255 以上算"可见差异"
    return ia.size, changed / total if total else 0.0


def main() -> int:
    work = Path(r"E:\OCR\work\render_check")
    work.mkdir(parents=True, exist_ok=True)

    for name in ("01_text_putnam", "02_formula_putnam", "03_table_gb_standard"):
        d = EXAMPLES / name
        case = json.loads((d / "case.json").read_text(encoding="utf-8"))
        role = case["reference_render_of"]
        text = next(c["text"] for c in case["candidates"] if c["role"] == role)

        cand = Candidate(
            case_id=name,
            image_path=str(d / case["block_image"]),
            text=text,
            category=case["category"],
        )
        results = render_candidates([cand], work_dir=work / name)
        r = results[0]
        if not r.ok:
            print(f"[{name}] 渲染失败: {r.reason} {r.detail}")
            continue

        sizes, ratio = pixel_diff(Path(r.render_image_path), d / case["reference_render"])
        print(f"[{name}] 渲染成功 -> {Path(r.render_image_path).name}")
        print(f"    本机渲染尺寸={sizes[0]}  参考渲染尺寸={sizes[1]}  可见差异像素占比={ratio:.2%}")
        if r.katex_errors:
            print(f"    KaTeX 报错: {r.katex_errors[:2]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
