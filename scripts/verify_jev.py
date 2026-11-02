"""官方样例验证：打分 3 个官方 case，与 case.json 里的 observed_prob_yes 比对。

官方口径（SKILL_jev 7.2）：三条分数与参考值相差不超过 0.02 就算装对了。
HTTP 200 不算通过，/healthz 返回 ok 也只说明服务起来了。

用法:
    python E:\\OCR\\scripts\\verify_jev.py [--score-url http://127.0.0.1:18501]
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
import urllib.request
from pathlib import Path

EXAMPLES = Path(
    r"E:\OCR\sources\MiniCPM-OCR-main\scripts\minicpm-ocr-jev\examples"
)
CASES = ("01_text_putnam", "02_formula_putnam", "03_table_gb_standard")
TOLERANCE = 0.02


def b64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode()


def post(url: str, body: dict) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        return json.load(resp)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--score-url", default="http://127.0.0.1:18501")
    ap.add_argument("--case", action="append", default=None)
    args = ap.parse_args()

    cases = args.case or list(CASES)
    rows = []
    ok = True
    for name in cases:
        d = EXAMPLES / name
        case = json.loads((d / "case.json").read_text(encoding="utf-8"))
        role = case["reference_render_of"]
        text = next(c["text"] for c in case["candidates"] if c["role"] == role)
        expect = case["observed_prob_yes"][role]

        body = {
            "items": [
                {
                    "original_image": b64(d / case["block_image"]),
                    "render_image": b64(d / case["reference_render"]),
                    "ocr_text": text,
                }
            ]
        }
        out = post(f"{args.score_url}/v1/score", body)
        res = out["results"][0]
        if "error" in res and res["error"]:
            print(f"[{name}] 打分失败: {res['error']}")
            ok = False
            continue
        got = float(res["prob_1"])
        diff = abs(got - expect)
        passed = diff <= TOLERANCE
        ok = ok and passed
        rows.append((name, case["category"], role, expect, got, diff, passed))

    print(f"{'case':22} {'cat':8} {'role':14} {'expect':>8} {'got':>8} {'diff':>7}  result")
    for name, cat, role, expect, got, diff, passed in rows:
        print(f"{name:22} {cat:8} {role:14} {expect:8.5f} {got:8.5f} {diff:7.5f}  "
              f"{'PASS' if passed else 'FAIL'}")
    if not rows:
        print("没有任何 case 跑出结果")
        return 2
    print("\n总体:", "PASS（与官方参考值偏差 <= 0.02）" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
