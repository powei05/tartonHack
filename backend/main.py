from __future__ import annotations

from datetime import date, timedelta
from collections import Counter
import os
import uuid

import cv2
import requests
from ultralytics import YOLO

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

# ✅ 关键：必须用 backend.barcode_scanner（不要用 barcode_scanner）
from backend.barcode_scanner import decode_barcodes_from_bytes


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
# Project paths
# backend/main.py -> PROJECT_ROOT = repo root (tartonHack)
# ======================
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))            # .../tartonHack/backend
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))     # .../tartonHack

# ======================
# Uploads (serve static)
# Render 上项目目录通常不可写，/tmp 可写
# ======================
IS_RENDER = bool(os.environ.get("RENDER")) or bool(os.environ.get("RENDER_SERVICE_ID"))
UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "/tmp/uploads" if IS_RENDER else os.path.join(PROJECT_ROOT, "uploads"))
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

# ======================
# Model Path (robust)
# 优先用环境变量 MODEL_PATH；否则用 repo_root/model/best.pt
# ======================
DEFAULT_MODEL_PATH = os.path.join(PROJECT_ROOT, "model", "best.pt")
MODEL_PATH = os.path.abspath(os.environ.get("MODEL_PATH", DEFAULT_MODEL_PATH))

if not os.path.exists(MODEL_PATH):
    raise FileNotFoundError(
        f"[YOLO] Model weights not found.\n"
        f"MODEL_PATH={MODEL_PATH}\n"
        f"Tip: put best.pt at {DEFAULT_MODEL_PATH} OR set env MODEL_PATH to the real path."
    )

MODEL = YOLO(MODEL_PATH, task="detect")
print("[YOLO] Loaded weights:", MODEL_PATH)
print("[YOLO] Classes:", MODEL.names)


# ======================
# Expiry rules & category map
# ======================
EXPIRY_RULES = {
    "Meat": 7,
    "Seafood": 3,
    "Vegetables": 10,
    "Fruit": 7,
    "Dairy": 14,
    "Cheese": 30,
    "Eggs": 21,
    "Grains": 7,
    "Pantry": 90,
    "Processed": 14,
    "Others": 5,
}

CATEGORY_MAP = {
    "fish": "Seafood", "seafood": "Seafood", "seaweed": "Seafood",

    "beef": "Meat", "chicken": "Meat", "pork": "Meat", "meat": "Meat",

    "processed_meat": "Processed", "hot dog": "Processed", "processed_food": "Processed",
    "kimchi": "Processed", "pickle": "Processed", "tofu": "Processed",
    "sandwich": "Processed", "pizza": "Processed", "cake": "Processed",

    "dairy": "Dairy", "butter": "Dairy",

    "bread": "Grains", "noodles": "Grains", "pasta": "Grains",
    "wheat": "Grains", "cereal": "Grains",

    "honey": "Pantry", "oil": "Pantry", "olive": "Pantry", "sauce": "Pantry",
    "seasoning": "Pantry", "spice": "Pantry", "nuts": "Pantry", "chocolate": "Pantry",
    "coffee": "Pantry", "juice": "Pantry", "garlic": "Pantry", "ginger": "Pantry",

    "broccoli": "Vegetables", "carrot": "Vegetables", "onion": "Vegetables",
    "tomato": "Vegetables", "spinach": "Vegetables", "taro": "Vegetables",
    "turnip": "Vegetables", "zucchini": "Vegetables", "potato": "Vegetables",

    "apple": "Fruit", "banana": "Fruit", "citrus": "Fruit", "strawberry": "Fruit",
    "watermelon": "Fruit", "mango": "Fruit", "kiwi": "Fruit", "grape": "Fruit",

    "cheese": "Cheese",
    "egg": "Eggs",
}

def _norm_label(label: str) -> str:
    return (label or "").strip().lower()

def _infer_to_items(image_fs_path: str, image_url: str, base_id: str, conf: float = 0.20):
    results = MODEL(image_fs_path, conf=conf)

    detected_labels = []
    detected_image_url = None

    for r in results:
        im_array = r.plot()
        det_filename = f"{base_id}_detected.jpg"
        det_fs_path = os.path.join(UPLOAD_DIR, det_filename)
        cv2.imwrite(det_fs_path, im_array)
        detected_image_url = f"/uploads/{det_filename}"

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
                    "barcode": None,
                    "name": label,
                    "image": image_url,
                    "category": category,
                    "added_at": today.strftime("%Y-%m-%d"),
                    "expire_at": expire_date.strftime("%Y-%m-%d"),
                    "status": "in_fridge",
                    "consumed_at": None,
                }
            )

    return items, detected_image_url, dict(counts)


@app.get("/")
def root():
    return {"ok": True, "msg": "Fridge backend is running. Visit /docs"}

@app.get("/health")
def health():
    return {"ok": True, "service": "backend"}


@app.post("/api/scan")
async def scan(image: UploadFile = File(...)):
    if not image:
        raise HTTPException(status_code=400, detail="Missing file field 'image'")
    if image.content_type and not image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail=f"Unsupported content_type: {image.content_type}")

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

    items, detected_image_url, counts = await run_in_threadpool(
        _infer_to_items, image_fs_path, image_url, base_id, 0.20
    )

    return JSONResponse(
        {
            "items": items,
            "counts": counts,
            "image_url": image_url,
            "detected_image_url": detected_image_url,
        }
    )


@app.post("/api/scan_barcode")
async def scan_barcode(image: UploadFile = File(...)):
    if not image:
        raise HTTPException(status_code=400, detail="Missing file field 'image'")
    content = await image.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty image file")

    results = await run_in_threadpool(decode_barcodes_from_bytes, content)
    return {
        "barcodes": [r.data for r in results],
        "results": [{"type": r.type, "data": r.data, "rect": r.rect} for r in results],
    }


@app.get("/api/barcode/{code}")
def lookup_barcode(code: str):
    url = f"https://world.openfoodfacts.org/api/v2/product/{code}.json"
    r = requests.get(url, timeout=10)
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail="Barcode lookup failed")

    data = r.json()
    p = data.get("product")
    if not p:
        raise HTTPException(status_code=404, detail="Barcode not found")

    nutr = p.get("nutriments", {}) or {}
    return {
        "barcode": code,
        "name": p.get("product_name") or p.get("product_name_en") or "",
        "image": p.get("image_url") or "",
        "brands": p.get("brands") or "",
        "categories": p.get("categories") or "",
        "nova_group": p.get("nova_group"),
        "sugar_100g": nutr.get("sugars_100g"),
    }
