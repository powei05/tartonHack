import streamlit as st
import requests
import json
import os
import uuid
from datetime import datetime, timedelta

# =========================
# Paths (make frontend self-contained)
# =========================
FRONTEND_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(FRONTEND_DIR, "pantry.json")
ICON_PATH = os.path.join(FRONTEND_DIR, "fridge_icon.png")

# =========================
# Backend connection
# =========================
BACKEND_BASE = os.environ.get("BACKEND_BASE", "http://127.0.0.1:8000")

BACKEND_CAT_TO_UI = {
    # backend categories -> UI categories
    "Meat": "肉類 🥩",
    "Vegetables": "蔬果 🥦",
    "Fruit": "蔬果 🥦",
    "Eggs": "一般食品 📦",
    "Cheese": "乳製品 🥛",
    "Dairy": "乳製品 🥛",
    "Others": "一般食品 📦",
    # lowercase variants (backend may normalize)
    "meat": "肉類 🥩",
    "vegetables": "蔬果 🥦",
    "fruit": "蔬果 🥦",
    "eggs": "一般食品 📦",
    "cheese": "乳製品 🥛",
    "dairy": "乳製品 🥛",
    "others": "一般食品 📦",
}

def abs_backend_url(path: str) -> str:
    """Convert '/uploads/xx.jpg' to 'http://127.0.0.1:8000/uploads/xx.jpg'."""
    if not path:
        return None
    if path.startswith("http"):
        return path
    return BACKEND_BASE.rstrip("/") + path

def scan_image_via_backend(uploaded_file):
    """Send Streamlit camera image to backend /api/scan and return items."""
    url = f"{BACKEND_BASE}/api/scan"
    file_bytes = uploaded_file.getvalue()
    files = {
        "image": (
            uploaded_file.name or "photo.jpg",
            file_bytes,
            uploaded_file.type or "image/jpeg",
        )
    }
    r = requests.post(url, files=files, timeout=60)
    r.raise_for_status()
    data = r.json()

    items = data.get("items", [])
    for it in items:
        it["image"] = abs_backend_url(it.get("image"))
        raw_cat = it.get("category")
        it["category"] = BACKEND_CAT_TO_UI.get(raw_cat, raw_cat or "一般食品 📦")
    return items, data

# =========================
# Page
# =========================
st.set_page_config(page_title="Smart Fridge", page_icon="🥦")

# =========================
# Helpers (barcode mode)
# =========================
def get_product_info(barcode):
    """Fetch product info from OpenFoodFacts."""
    if len(barcode) < 3:
        return None
    url = f"https://world.openfoodfacts.org/api/v0/product/{barcode}.json"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == 1:
                return data["product"]
    except Exception as e:
        print(e)
    return None

def determine_category(api_data):
    """Auto category for OpenFoodFacts products."""
    if not api_data:
        return "其他 📦"

    categories = str(api_data.get("categories_tags", [])).lower()
    keywords = str(api_data.get("keywords", [])).lower()
    full_text = categories + keywords

    if any(x in full_text for x in ["milk", "dairy", "cheese", "yogurt", "乳", "優格"]):
        return "乳製品 🥛"
    elif any(x in full_text for x in ["meat", "chicken", "beef", "pork", "fish", "肉"]):
        return "肉類 🥩"
    elif any(x in full_text for x in ["vegetable", "plant", "fruit", "salad", "蔬", "果"]):
        return "蔬果 🥦"
    elif any(x in full_text for x in ["beverage", "drink", "soda", "juice", "water", "tea", "coffee", "飲", "茶", "水"]):
        return "飲料 🥤"
    elif any(x in full_text for x in ["snack", "chocolate", "chip", "candy", "cookie", "零食", "餅"]):
        return "零食 🍪"
    elif any(x in full_text for x in ["sauce", "condiment", "oil", "vinegar", "醬", "油"]):
        return "調味料 🧂"
    elif any(x in full_text for x in ["frozen", "ice", "凍"]):
        return "冷凍食品 🧊"
    else:
        return "一般食品 📦"

def create_pantry_item(api_data, scanned_barcode, user_image=None):
    """Create pantry item for barcode mode."""
    if api_data:
        api_image = api_data.get("image_front_small_url") or api_data.get("image_front_url")
        item_name = api_data.get("product_name", "未知商品")
        category = determine_category(api_data)
    else:
        api_image = None
        item_name = f"手動輸入 ({scanned_barcode})"
        category = "其他 📦"

    final_image = api_image if api_image else user_image
    today = datetime.now().date()
    default_expire = today + timedelta(days=7)

    return {
        "id": str(uuid.uuid4()),
        "barcode": scanned_barcode,
        "name": item_name,
        "image": final_image,
        "category": category,
        "added_at": today.strftime("%Y-%m-%d"),
        "expire_at": default_expire.strftime("%Y-%m-%d"),
        "status": "in_fridge",
        "consumed_at": None,
    }

# =========================
# Local "DB" (pantry.json)
# =========================
def save_pantry(pantry_list):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(pantry_list, f, indent=4, ensure_ascii=False)

def load_pantry():
    """Load pantry.json and auto-delete consumed items after 7 days."""
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        cleaned_data = []
        today = datetime.now().date()
        dirty = False

        for item in data:
            if item.get("status") == "consumed" and item.get("consumed_at"):
                consumed_date = datetime.strptime(item["consumed_at"], "%Y-%m-%d").date()
                days_passed = (today - consumed_date).days
                if days_passed > 7:
                    dirty = True
                    continue
            cleaned_data.append(item)

        if dirty:
            save_pantry(cleaned_data)

        return cleaned_data
    return []

if "pantry" not in st.session_state:
    st.session_state.pantry = load_pantry()

# =========================
# Dialog: manual entry
# =========================
@st.dialog("📝 手動新增食材")
def manual_entry_dialog():
    st.caption("適用於：剩菜、無條碼商品")
    name_input = st.text_input("商品名稱", placeholder="例如：媽媽煮的滷肉")
    category_options = [
        "一般食品 📦", "乳製品 🥛", "肉類 🥩", "蔬果 🥦",
        "飲料 🥤", "零食 🍪", "調味料 🧂", "冷凍食品 🧊", "熟食 🍲"
    ]
    category_input = st.selectbox("分類", category_options)
    today = datetime.now().date()
    expire_input = st.date_input("過期日", value=today + timedelta(days=3))

    if st.button("確認新增", type="primary"):
        if name_input:
            new_item = {
                "id": str(uuid.uuid4()),
                "barcode": "MANUAL",
                "name": name_input,
                "image": None,
                "category": category_input,
                "added_at": today.strftime("%Y-%m-%d"),
                "expire_at": expire_input.strftime("%Y-%m-%d"),
                "status": "in_fridge",
                "consumed_at": None,
            }
            st.session_state.pantry.append(new_item)
            save_pantry(st.session_state.pantry)
            st.success(f"已加入：{name_input}")
            st.rerun()
        else:
            st.warning("請輸入名稱")

# =========================
# UI start
# =========================
col_logo, col_title = st.columns([1, 5])
with col_logo:
    if os.path.exists(ICON_PATH):
        st.image(ICON_PATH, width=60)
    else:
        st.write("🥦")
with col_title:
    st.title("智慧冰箱")

st.write("---")

col_tabs, col_manual_btn = st.columns([3, 1])
with col_manual_btn:
    st.write("")
    if st.button("➕ 手動輸入"):
        manual_entry_dialog()

with col_tabs:
    tab1, tab2 = st.tabs(["📸 拍照掃描", "⌨️ Barcode 輸入"])

    # ---------- Tab 1: Photo -> Backend YOLO ----------
    with tab1:
        camera_photo = st.camera_input("點擊拍照", key="camera_scan", label_visibility="collapsed")
        if camera_photo:
            st.success("影像已擷取！")
            if st.button("送去辨識並加入冰箱", key="btn_cam_add"):
                try:
                    items, raw = scan_image_via_backend(camera_photo)

                    if not items:
                        st.warning("模型没有识别到物品（items 为空）。换张更清晰/更近的照片试试。")
                    else:
                        st.session_state.pantry.extend(items)
                        save_pantry(st.session_state.pantry)
                        st.success(f"已加入 {len(items)} 項")

                    with st.expander("debug: backend response"):
                        st.json(raw)

                    st.rerun()
                except Exception as e:
                    st.error(f"后端识别失败：{e}")

    # ---------- Tab 2: Barcode -> OpenFoodFacts ----------
    with tab2:
        manual_code = st.text_input("輸入 Barcode", placeholder="例如: 5449000000996", key="manual_code")
        if st.button("查詢並加入", key="btn_manual_add"):
            if manual_code:
                raw_product = get_product_info(manual_code)
                if raw_product:
                    new_item = create_pantry_item(raw_product, manual_code)
                    st.session_state.pantry.append(new_item)
                    save_pantry(st.session_state.pantry)
                    st.rerun()
                else:
                    st.error("找不到此商品")

st.divider()

# =========================
# Main list (in_fridge)
# =========================
active_items = [item for item in st.session_state.pantry if item.get("status") == "in_fridge"]
all_categories = ["全部"] + sorted(list(set(item.get("category", "其他 📦") for item in active_items)))

st.subheader("❄️ 我的冰箱")
selected_category = st.radio(
    "篩選分類：",
    all_categories,
    horizontal=True,
    label_visibility="collapsed",
)

if selected_category == "全部":
    filtered_pantry = active_items
else:
    filtered_pantry = [item for item in active_items if item.get("category") == selected_category]

st.caption(f"目前顯示: {selected_category} ({len(filtered_pantry)} 項)")

if not filtered_pantry and selected_category != "全部":
    st.info(f"你的冰箱裡沒有 {selected_category} 喔！")

for item in filtered_pantry:
    original_index = st.session_state.pantry.index(item)
    expire_date = datetime.strptime(item["expire_at"], "%Y-%m-%d").date()
    days_left = (expire_date - datetime.now().date()).days
    item_category = item.get("category", "一般 📦")

    with st.container(border=True):
        c1, c2, c3 = st.columns([1.5, 3.5, 1])

        with c1:
            if item.get("image") and str(item["image"]).startswith("http"):
                st.image(item["image"], width=80)
            else:
                st.markdown("<div style='text-align: center; font-size: 40px;'>📦</div>", unsafe_allow_html=True)

        with c2:
            st.markdown(f"**{item.get('name', 'unknown')}**")
            st.caption(f"{item_category} • {item.get('expire_at')}")

            if days_left < 3:
                st.markdown(f":red[⚠️ 剩 {days_left} 天]")
            else:
                st.markdown(f":green[✅ 剩 {days_left} 天]")

        with c3:
            st.write("")
            st.write("")
            if st.button("🍽️", key=f"eat_{item['id']}"):
                st.session_state.pantry[original_index]["status"] = "consumed"
                st.session_state.pantry[original_index]["consumed_at"] = datetime.now().strftime("%Y-%m-%d")
                save_pantry(st.session_state.pantry)
                st.rerun()

# =========================
# Recently consumed
# =========================
consumed_items = [item for item in st.session_state.pantry if item.get("status") == "consumed"]

if consumed_items:
    st.markdown("---")
    st.subheader(f"🥣 近期已完食 ({len(consumed_items)})")
    st.caption("這裡會保留 7 天，或是你可以手動刪除。")

    for item in consumed_items:
        original_index = st.session_state.pantry.index(item)

        with st.container():
            col_a, col_b, col_c = st.columns([1, 3, 1])

            with col_a:
                if item.get("image") and str(item["image"]).startswith("http"):
                    st.image(item["image"], width=40)
                else:
                    st.write("🥣")

            with col_b:
                st.write(f"~~{item.get('name', 'unknown')}~~")
                st.caption(f"完食於: {item.get('consumed_at')}")

            with col_c:
                if st.button("↩️", key=f"restore_{item['id']}", help="放回冰箱"):
                    st.session_state.pantry[original_index]["status"] = "in_fridge"
                    st.session_state.pantry[original_index]["consumed_at"] = None
                    save_pantry(st.session_state.pantry)
                    st.rerun()

                if st.button("❌", key=f"del_{item['id']}", help="永久刪除"):
                    st.session_state.pantry.pop(original_index)
                    save_pantry(st.session_state.pantry)
                    st.rerun()

            st.divider()
