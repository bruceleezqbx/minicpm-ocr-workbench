"""生成一张用于验证 MiniCPM-OCR 整页解析的测试图：中文正文 + 表格 + 公式 + 手写签名 + 红色印章。
输出: E:\\OCR\\work\\sample_doc.png
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT = Path(r"E:\OCR\work\sample_doc.png")
OUT.parent.mkdir(parents=True, exist_ok=True)

W, H = 1240, 1754  # A4 @150dpi
img = Image.new("RGB", (W, H), "white")
d = ImageDraw.Draw(img)


def font(name, size):
    for p in (
        rf"C:\Windows\Fonts\{name}",
        r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\simhei.ttf",
    ):
        if Path(p).exists():
            try:
                return ImageFont.truetype(p, size)
            except OSError:
                continue
    return ImageFont.load_default()


f_title = font("msyhbd.ttc", 46)
f_body = font("msyh.ttc", 30)
f_small = font("msyh.ttc", 24)
f_hand = font("segoepr.ttf", 46)
f_mono = font("consola.ttf", 30)

y = 90
d.text((120, y), "设备采购合同（样例）", font=f_title, fill="black")
y += 80
d.text((120, y), "合同编号：HT-2026-0918    甲方：华信制造有限公司", font=f_body, fill="black")
y += 48
d.text((120, y), "乙方：远达电子科技有限公司", font=f_body, fill="black")
y += 70

para = [
    "根据双方签订的框架协议，现就下列设备的采购事宜达成如下条款：",
    "1. 本合同总金额为人民币 1,286,400.00 元（大写：壹佰贰拾捌万陆仟肆佰元整）。",
    "2. 交付日期为 2026 年 11 月 30 日前，逾期按每日 0.05% 支付违约金。",
    "3. 验收标准以 GB/T 2828.1-2012 规定的抽样检验结果为准。",
]
for line in para:
    d.text((120, y), line, font=f_body, fill="black")
    y += 46

y += 20
d.text((120, y), "表 1  设备清单与报价", font=f_body, fill="black")
y += 50

# 表格
rows = [
    ["序号", "设备名称", "数量", "单价(元)", "小计(元)"],
    ["1", "工业相机 Basler ace2", "12", "48,500.00", "582,000.00"],
    ["2", "光源 LED 环形补光", "12", "6,800.00", "81,600.00"],
    ["3", "标定板 9x9 棋盘格", "4", "3,200.00", "12,800.00"],
    ["4", "边缘计算单元 IPC-5000", "6", "101,666.67", "610,000.00"],
]
col_x = [120, 200, 640, 790, 1000]
row_h = 56
for i, row in enumerate(rows):
    top = y + i * row_h
    if i == 0:
        for cx, cell in zip(col_x, row):
            d.rectangle([cx, top, cx + (col_x[1]-col_x[0] if cx==col_x[0] else 0), top + row_h], fill=(230, 230, 230))
    for j, cell in enumerate(row):
        x = col_x[j]
        d.text((x + 16, top + 14), cell, font=f_small, fill="black")
    # 表格线
    d.line([col_x[0], top + row_h, col_x[-1] + 160, top + row_h], fill="black", width=2)
for j, cx in enumerate(col_x):
    bottom = y + len(rows) * row_h
    d.line([cx, y, cx, bottom], fill="black", width=2)
d.line([col_x[-1] + 160, y, col_x[-1] + 160, bottom], fill="black", width=2)
y = bottom + 56

d.text((120, y), "4. 本合同价款计算公式如下：", font=f_body, fill="black")
y += 56
d.text((160, y), "Total = sum(q_i * p_i) + 0.05% * Days * Total", font=f_mono, fill="black")
y += 56
d.text((160, y), "T = \\frac{\\sum_{i=1}^{n} q_i p_i}{1 - r}", font=f_mono, fill="black")
y += 90

# 手写签名
d.text((160, y), "甲方代表（签字）：", font=f_body, fill="black")
d.text((520, y - 14), "Zhang Wei", font=f_hand, fill=(20, 30, 90))
y += 70
d.text((160, y), "乙方代表（签字）：", font=f_body, fill="black")
d.text((520, y - 14), "L. Chen", font=f_hand, fill=(20, 30, 90))

# 红色印章
stamp = Image.new("RGBA", (240, 240), (0, 0, 0, 0))
sd = ImageDraw.Draw(stamp)
sd.ellipse([8, 8, 232, 232], outline=(198, 30, 30, 230), width=7)
sd.ellipse([28, 28, 212, 212], outline=(198, 30, 30, 200), width=3)
sd.text((52, 100), "华信制造", font=font("simhei.ttf", 34), fill=(198, 30, 30, 230))
sd.text((58, 146), "合同专用章", font=font("simhei.ttf", 26), fill=(198, 30, 30, 230))
stamp = stamp.rotate(-14, resample=Image.BICUBIC)
img.paste(stamp, (880, y - 40), stamp)

# 轻微做旧：模拟翻拍/扫描
img = img.rotate(0.6, resample=Image.BICUBIC, fillcolor="white")
img = img.filter(ImageFilter.GaussianBlur(radius=0.35))
img = img.convert("RGB").save(OUT, quality=95)
print("saved:", OUT, OUT.stat().st_size)
