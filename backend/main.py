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
# Project paths
# backend/main.py -> PROJECT_ROOT = repo root (tartonHack)
# ======================
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))               # .../tartonHack/backend
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))        # .../tartonHack


# ======================
# Uploads (serve static)
# Render 上项目目录通常不可写，/tmp 可写
# 也支持用环境变量 UPLOAD_DIR 覆盖
# ======================
UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "/tmp/uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


# ======================
# Model Path (robust)
# 优先用环境变量 MODEL_PATH；否则用 repo_root/model/best.pt
# ======================
DEFAULT_MODEL_PATH = os.path.join(PROJECT_ROOT, "model", "best.pt")
MODEL_PATH = os.environ.get("MODEL_PATH", DEFAULT_MODEL_PATH)
MODEL_PATH = os.path.abspath(MODEL_PATH)

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
    "Meat": 7,          # 生肉類 (縮短至1週較安全)
    "Seafood": 3,       # 海鮮類 (期限最短)
    "Vegetables": 10,   # 蔬菜類
    "Fruit": 7,         # 水果類
    "Dairy": 14,        # 乳製品 (鮮乳、奶油等)
    "Cheese": 30,       # 起司類 (發酵乳酪通常較久)
    "Eggs": 21,         # 蛋類
    "Grains": 7,        # 麵包、麵條、米製品
    "Pantry": 90,       # 調味料、乾貨、油品 (期限長)
    "Processed": 14,    # 加工食品、微波食品
    "Others": 5,        # 其他
}

# YOLO label -> business category
CATEGORY_MAP = {
    # --- Seafood (海鮮: 3天) ---
    "fish": "Seafood", "seafood": "Seafood", "seaweed": "Seafood",
    
    # --- Meat (肉類: 7天) ---
    "beef": "Meat", "chicken": "Meat", "pork": "Meat", "poultry": "Meat", 
    "meat": "Meat", "poultry": "Meat",

    # --- Processed (加工食品: 14天) ---
    "processed_meat": "Processed", "hot dog": "Processed", "processed_food": "Processed",
    "kimchi": "Processed", "pickle": "Processed", "tofu": "Processed",
    "sandwich": "Processed", "pizza": "Processed", "cake": "Processed",

    # --- Dairy (乳製品: 14天) ---
    "dairy": "Dairy", "butter": "Dairy",
    
    # --- Grains (糧食/麵點: 7天) ---
    "bread": "Grains", "noodles": "Grains", "pasta": "Grains", 
    "rice_product": "Grains", "wheat": "Grains", "cereal": "Grains",
    
    # --- Pantry (乾貨/調料: 90天) ---
    "honey": "Pantry", "oil": "Pantry", "olive": "Pantry", "sauce": "Pantry", 
    "seasoning": "Pantry", "spice": "Pantry", "nuts": "Pantry", "chocolate": "Pantry",
    "coffee": "Pantry", "juice": "Pantry", "garlic": "Pantry", "ginger": "Pantry",
    
    # --- Vegetables (蔬菜: 10天) ---
    "artichoke": "Vegetables", "asparagus": "Vegetables", "bamboo_shoots": "Vegetables",
    "beans": "Vegetables", "beetroot": "Vegetables", "broccoli": "Vegetables",
    "cabbage": "Vegetables", "cactus": "Vegetables", "carrot": "Vegetables",
    "cassava": "Vegetables", "cauliflower": "Vegetables", "corn": "Vegetables",
    "cucumber": "Vegetables", "eggplant": "Vegetables", "gourd": "Vegetables",
    "herbs": "Vegetables", "leafy_greens": "Vegetables", "lentils": "Vegetables",
    "lettuce": "Vegetables", "moringa": "Vegetables", "mushroom": "Vegetables",
    "okra": "Vegetables", "onion": "Vegetables", "peas": "Vegetables",
    "pepper": "Vegetables", "potato": "Vegetables", "pumpkin": "Vegetables",
    "radish": "Vegetables", "spinach": "Vegetables", "taro": "Vegetables",
    "tomato": "Vegetables", "turnip": "Vegetables", "zucchini": "Vegetables",
    "avocado": "Vegetables",
    
    # --- Fruit (水果: 7天) ---
    "apple": "Fruit", "banana": "Fruit", "citrus": "Fruit", "fruit": "Fruit",
    "grape": "Fruit", "jackfruit": "Fruit", "kiwi": "Fruit", "mango": "Fruit",
    "papaya": "Fruit", "pear": "Fruit", "pineapple": "Fruit", "plum": "Fruit",
    "pomegranate": "Fruit", "strawberry": "Fruit", "watermelon": "Fruit",
    
    # --- 原有類別 ---
    "cheese": "Cheese",
    "egg": "Eggs"
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
        # 保存带框图（很利于调试）
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
                    "barcode": None,
                    "name": label,
                    "image": image_url,      # 原图 URL（/uploads/xxx.jpg）
                    "category": category,    # Meat/Fruit/...
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
