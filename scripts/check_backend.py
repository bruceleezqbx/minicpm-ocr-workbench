"""后端连通性验证：发一张真实文字裁剪图给识别服务，确认能返回非空文本。
用法: python E:\\OCR\\scripts\\check_backend.py [backend]
"""
import os
import sys
from copy import deepcopy

from PIL import Image

from minicpmvocr import DEFAULT_CONFIG, create_backend

backend = sys.argv[1] if len(sys.argv) > 1 else "ollama"
img_path = r"E:\OCR\work\sample_doc.png"

cfg = deepcopy(DEFAULT_CONFIG)
cfg["engine"].update({
    "type": backend,
    "server_url": os.environ.get("OCR_TEST_URL", "http://127.0.0.1:18499"),
    "model_name": os.environ.get("OCR_TEST_MODEL", "minicpm-ocr"),
    "max_model_len": int(os.environ.get("OCR_MAX_LEN", "8192")),
    "startup_timeout_sec": 120,
    "request_ready_timeout_sec": 60,
})
if backend == "ollama":
    cfg["engine"]["num_ctx"] = int(os.environ.get("OCR_NUM_CTX", "8192"))

client = create_backend(cfg)
client.wait_ready(timeout_sec=120)

with Image.open(img_path) as image:
    crop = image.crop((100, 80, 1140, 320)).convert("RGB")
    result = client.recognize(crop, "Text Recognition:", max_new_tokens=1024)

text = result.get("text", "")
print("---- recognized ----")
print(text)
print("---- meta ----")
print("finish_reason:", result.get("finish_reason"))
print("chars:", len(text.strip()))
assert text.strip(), "空输出：OCR 未识别出任何文字"
print("OK: backend", backend, "返回非空结果")
