import os
from ultralytics import YOLO
from datetime import datetime, timedelta
from collections import Counter
import json
import uuid
from huggingface_hub import hf_hub_download
import cv2
# 1. 載入模型 (YOLOv8 Nano)
current_dir = os.path.dirname(os.path.abspath(__file__))
model_path = os.path.join(current_dir, "best.pt")
model = YOLO(model_path, task='detect' )
# print(model.names)
# 2. 定義保存期限規則 (單位：天)
# 這裡根據你的需求設定：肉品 21天(3週), 蔬菜 14天(2週), 起司 30天(1個月)
EXPIRY_RULES = {
    "Meat": 21,
    "Vegetables": 14,
    "Cheese": 30,
    "Fruit": 7,
    "Eggs": 21,
    "Others": 5,
    
}

# 3. 定義標籤對應類別 (將 YOLO 的 COCO 標籤映射到我們的規則)
# 註：yolov8n 預設標籤包含 apple, broccoli, carrot, pizza 等
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
    "citron": "Fruit",
    # 根據你的需要持續增加標籤...
}

# 4. 進行辨識
img_path = os.path.join(current_dir, 'food/test4.jpg') # 請替換成你的圖片路徑
results = model(img_path, conf=0.08)  # conf 是置信度閾值，可以根據需要調整

# 5. 統計偵測到的品項數量
detected_items = []
for r in results:
    # 繪製並儲存辨識結果圖片 (包含框線與標籤)
    im_array = r.plot()  # 取得繪製後的影像陣列 (BGR 格式)
    detected_image_path = os.path.join(current_dir, 'detected_food.jpg')
    cv2.imwrite(detected_image_path, im_array)
    for c in r.boxes.cls:
        label = model.names[int(c)] # 取得標籤名稱 (例如: 'apple')
        detected_items.append(label)

item_counts = Counter(detected_items)

# 6. 計算並印出結果
print(f"--- 冰箱物資清單 ({datetime.now().strftime('%Y-%m-%d')}) ---")
print(f"{'品項':<15} | {'數量':<5} | {'建議保存期限':<15}")
print("-" * 45)

inventory_list = []

for item, count in item_counts.items():
    # 判斷類別，若不在 map 中則歸類為 Others
    category = CATEGORY_MAP.get(item, "Others")
    
    # 計算日期：今天 + 規則天數
    expiry_days = EXPIRY_RULES.get(category)
    expiry_date = datetime.now() + timedelta(days=expiry_days)
    expiry_str = expiry_date.strftime('%Y-%m-%d')
    
    print(f"{item:<15} | {count:<5} | {expiry_str} ({category})")

    # 依照數量產生個別項目的 JSON (符合指定的 Schema)
    for _ in range(count):
        inventory_list.append({
            "id": str(uuid.uuid4()),
            "barcode": "",
            "name": item,
            "image": img_path,
            "category": category,
            "added_at": datetime.now().strftime('%Y-%m-%d'),
            "expire_at": expiry_str,
            "status": "in_fridge",
            "consumed_at": None
        })

# 輸出 JSON 結果
print("\n--- JSON Output ---")
print(json.dumps(inventory_list, indent=4, ensure_ascii=False))

# 儲存 JSON 到檔案
json_filename = os.path.join(current_dir, "inventory.json")
with open(json_filename, "w", encoding="utf-8") as f:
    json.dump(inventory_list, f, indent=4, ensure_ascii=False)
print(f"\n[系統提示] JSON 資料已儲存至 {json_filename}")
print(f"[系統提示] 辨識結果圖片已儲存至 {detected_image_path} (請開啟此圖片查看辨識框)")
