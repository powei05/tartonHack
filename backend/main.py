from datetime import date, timedelta
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import uuid
import os

app = FastAPI(title="Fridge Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# 让前端能访问你保存的图片：http://127.0.0.1:8000/uploads/<filename>
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


def normalize_category(cat: str) -> str:
    mapping = {
        "Eggs": "eggs",
        "Vegetables": "vegetables",
        "Fruits": "fruits",
        "Dairy": "dairy",
        "Meat": "meat",
        "leafy_greens": "vegetables",
    }
    return mapping.get(cat, (cat or "unknown").strip().lower())


def normalize_items(recognized_items: list[dict], image_url: str) -> list[dict]:
    out = []
    for it in recognized_items:
        barcode = it.get("barcode")
        if barcode == "":
            barcode = None

        out.append(
            {
                "id": it.get("id") or str(uuid.uuid4()),
                "barcode": barcode,
                "name": it.get("name") or "unknown",
                "image": image_url,  # 关键：统一用后端保存的可访问 URL
                "category": normalize_category(it.get("category", "unknown")),
                "added_at": it.get("added_at") or date.today().strftime("%Y-%m-%d"),
                "expire_at": it.get("expire_at") or date.today().strftime("%Y-%m-%d"),
                "status": it.get("status") or "in_fridge",
                "consumed_at": it.get("consumed_at"),
            }
        )
    return out


@app.get("/health")
def health():
    return {"ok": True, "service": "backend"}


@app.post("/api/scan")
async def scan(image: UploadFile = File(...)):
    # 1) 保存图片到本地
    item_id = str(uuid.uuid4())
    ext = os.path.splitext(image.filename or "")[1].lower() or ".jpg"
    filename = f"{item_id}{ext}"
    path = os.path.join(UPLOAD_DIR, filename)

    content = await image.read()
    with open(path, "wb") as f:
        f.write(content)

    image_url = f"/uploads/{filename}"

    # 2) 假识别结果（先跑通链路）——之后替换成你们视觉识别模块返回的 items list
    # 视觉识别模块示例返回格式（list[dict]）：
    recognized_items = [
        {
            "id": None,
            "barcode": "",
            "name": "egg",
            "image": "food/test1.jpg",
            "category": "Eggs",
            "added_at": date.today().strftime("%Y-%m-%d"),
            "expire_at": (date.today() + timedelta(days=21)).strftime("%Y-%m-%d"),
            "status": "in_fridge",
            "consumed_at": None,
        }
    ]

    # 3) 统一输出结构（修正 image/category/barcode 等）
    items = normalize_items(recognized_items, image_url)

    # 你可以选择返回一个 item（单物品）或返回 items 列表（更贴合识别模块）
    return JSONResponse({"items": items})


# 可选：调试用；嫌吵可以删掉
print(">>> backend.main loaded, app=", app)
