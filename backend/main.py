from datetime import date, timedelta
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

import os
import uuid
from collections import Counter

import cv2
from ultralytics import YOLO


# ======================
# App & CORS
# ======================
app = FastAPI(title="Fridge Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ======================
# Uploads (serve static)
# ======================
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


# ======================
# Model Path (robust)
# ======================
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))            # .../backend
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)                         # .../tartonHack

# 优先用环境变量 MODEL_PATH；否则默认用项目根目录的 model/best.pt
DEFAULT_MODEL_PATH = os.path.join(PROJECT_ROOT, "model", "best.pt")
MODEL_PATH = os.environ.get("MODEL_PATH", DEFAULT_MODEL_PATH)

if not os.path.exists(MODEL_PATH):
    raise FileNotFoundError(
        f"[YOLO] Model weights not found.\n"
        f"MODEL_PATH={MODEL_PATH}\n"
        f"Tip: put best.pt at {DEFAULT_MODEL_PATH} OR set env MODEL_PATH to the real path."
    )

# load once
MODEL = YOLO(MODEL_PATH, task="detect")
print("[YOLO] Loaded weights:", MODEL_PATH)
print("[YOLO] Classes:", MODEL.names)


# ======================
# Expiry rules & category map
# ======================
EXPIRY_RULES = {
    "Meat": 21,
    "Vegetables": 14,
    "Cheese": 30,
    "Fruit": 7,
    "Eggs": 21,
    "Others": 5,
}

# YOLO label -> business category
CATEGORY_MAP = {
    "apple": "Fruit",
    "banana": "Fruit",
    "orange": "Fruit",
    "broccoli": "Vegetables",
    "carrot": "Vegetables",
    "sandwich": "Others",
    "pizza": "Others",
    "cake": "Others",
    "hot dog": "Meat",
    "egg": "Eggs",
    "onion": "Vegetables",
    "tomato": "Vegetables",
}


def _norm_label(label: str) -> str:
    """统一 label，避免大小写/空格导致映射不到"""
    return (label or "").strip().lower()


def _infer_to_items(image_fs_path: str, image_url: str, base_id: str, conf: float = 0.20):
    """
    同步函数：跑 YOLO 推理 + 生成 items 列表 + 输出带框图
    放到线程池跑，避免阻塞 FastAPI event loop
    """
    results = MODEL(image_fs_path, conf=conf)

    detected_labels = []
    detected_image_url = None

    for r in results:
        # 保存带框图（可选，但很利于调试）
        im_array = r.plot()  # BGR ndarray
        det_filename = f"{base_id}_detected.jpg"
        det_fs_path = os.path.join(UPLOAD_DIR, det_filename)
        cv2.imwrite(det_fs_path, im_array)
        detected_image_url = f"/uploads/{det_filename}"

        # 收集 labels
        for c in r.boxes.cls:
            label = MODEL.names[int(c)]
            detected_labels.append(_norm_label(label))

    counts = Counter(detected_labels)
    today = date.today()

    items = []
    for label, count in counts.items():
        category = CATEGORY_MAP.get(label, "Others")
        expiry_days = EXPIRY_RULES.get(category, EXPIRY_RULES["Others"])
        expire_date = today + timedelta(days=expiry_days)

        for _ in range(count):
            items.append(
                {
                    "id": str(uuid.uuid4()),
                    "barcode": None,              # 后续扫码再填
                    "name": label,                # 这里用 YOLO label（归一化后）
                    "image": image_url,           # 统一用后端 URL
                    "category": category,         # 业务大类（Meat/Fruit/...）
                    "added_at": today.strftime("%Y-%m-%d"),
                    "expire_at": expire_date.strftime("%Y-%m-%d"),
                    "status": "in_fridge",
                    "consumed_at": None,
                }
            )

    return items, detected_image_url, dict(counts)


@app.get("/health")
def health():
    return {"ok": True, "service": "backend"}


@app.post("/api/scan")
async def scan(image: UploadFile = File(...)):
    # basic validation
    if not image:
        raise HTTPException(status_code=400, detail="Missing file field 'image'")
    if image.content_type and not image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail=f"Unsupported content_type: {image.content_type}")

    # 1) 保存上传图片
    base_id = str(uuid.uuid4())
    ext = os.path.splitext(image.filename or "")[1].lower() or ".jpg"
    filename = f"{base_id}{ext}"
    image_fs_path = os.path.join(UPLOAD_DIR, filename)

    content = await image.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty image file")

    with open(image_fs_path, "wb") as f:
        f.write(content)

    image_url = f"/uploads/{filename}"

    # 2) 跑模型（线程池）
    items, detected_image_url, counts = await run_in_threadpool(
        _infer_to_items, image_fs_path, image_url, base_id, 0.20
    )

    # 3) 返回结果（items schema 稳定）
    return JSONResponse(
        {
            "items": items,
            "counts": counts,
            "image_url": image_url,
            "detected_image_url": detected_image_url,
        }
    )
## 185行到291行爲barcode辨識相關code BY Bonnie
## scan_barcode , _infer_business_category_from_off和 barcode_lookup

from barcode_scanner import decode_barcodes_from_bytes

@app.post("/api/scan_barcode")
async def scan_barcode(image: UploadFile = File(...)):
    content = await image.read()
    try:
        results = decode_barcodes_from_bytes(content)
        return {"barcodes": [{"type": r.type, "data": r.data} for r in results]}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


from typing import Optional
from datetime import date, timedelta
import uuid
import requests
from fastapi import HTTPException

# 你原本應該就有 EXPIRY_RULES，沒有的話先加這個（或沿用你已有的）
# EXPIRY_RULES = {"Meat": 21, "Vegetables": 14, "Cheese": 30, "Fruit": 7, "Eggs": 21, "Others": 5}

def _infer_business_category_from_off(product: dict) -> str:
    """
    OpenFoodFacts -> 业务类别（与你 EXPIRY_RULES 对齐）
    回传: Meat / Vegetables / Fruit / Eggs / Cheese / Others
    """
    name = (product.get("product_name") or product.get("product_name_en") or "").lower()
    cats = product.get("categories_tags") or []
    cats = [str(c).lower() for c in cats]

    def has_any(keys):
        return any(any(k in c for k in keys) for c in cats) or any(k in name for k in keys)

    if has_any(["egg", "eggs"]):
        return "Eggs"
    if has_any(["cheese", "dairy", "milk", "yogurt", "butter", "cream"]):
        return "Cheese"
    if has_any(["meat", "beef", "pork", "chicken", "sausage", "ham", "bacon", "turkey", "hot-dogs", "hot dog"]):
        return "Meat"
    if has_any(["vegetable", "vegetables", "onion", "tomato", "carrot", "broccoli", "salad"]):
        return "Vegetables"
    if has_any(["fruit", "fruits", "apple", "banana", "orange", "berry", "grape"]):
        return "Fruit"

    return "Others"


@app.get("/api/barcode/{code}")
def barcode_lookup(code: str):
    code = (code or "").strip()

    # 你的條碼是 0855... 這種，前面 0 也算數，所以不要用 int
    if not code.isdigit() or len(code) < 8:
        raise HTTPException(status_code=400, detail="Invalid barcode. Expect digits with length >= 8.")

    off_url = f"https://world.openfoodfacts.org/api/v2/product/{code}.json"

    try:
        r = requests.get(off_url, timeout=10)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"OpenFoodFacts request failed: {e}")

    if r.status_code != 200:
        raise HTTPException(status_code=502, detail=f"OpenFoodFacts bad status: {r.status_code}")

    data = r.json()
    product = data.get("product")
    if not product:
        raise HTTPException(status_code=404, detail="Product not found for this barcode.")

    name = (
        product.get("product_name")
        or product.get("product_name_en")
        or product.get("generic_name")
        or "unknown"
    ).strip()

    image_url = (
        product.get("image_url")
        or product.get("image_front_url")
        or product.get("selected_images", {}).get("front", {}).get("display", {}).get("en")
        or None
    )

    category = _infer_business_category_from_off(product)
    expiry_days = EXPIRY_RULES.get(category, EXPIRY_RULES.get("Others", 5))
    today = date.today()
    expire_date = today + timedelta(days=expiry_days)

    item = {
        "id": str(uuid.uuid4()),
        "barcode": code,
        "name": name,
        "image": image_url,
        "category": category,  # Meat/Fruit/Vegetables/Eggs/Cheese/Others
        "added_at": today.strftime("%Y-%m-%d"),
        "expire_at": expire_date.strftime("%Y-%m-%d"),
        "status": "in_fridge",
        "consumed_at": None,
    }

    return {"item": item}
