import streamlit as st
import requests
import json
import os
import uuid
from datetime import datetime, timedelta

# =========================
# 🔧 Settings & Constants
# =========================
# Backend API URL (Ensure FastAPI is running on port 8000)
BACKEND_URL = "http://127.0.0.1:8000"

# Streamlit Page Configuration
st.set_page_config(page_title="Fridge Assistant", page_icon="🥦")

# Local Database File
DB_FILE = "pantry.json"

# --- Category Mapping (Backend English -> UI Display) ---
CATEGORY_MAP = {
    "eggs": "Eggs 🥚",
    "vegetables": "Vegetables 🥦",
    "fruits": "Fruits 🍎",
    "dairy": "Dairy 🥛",
    "meat": "Meat 🥩",
    "beverage": "Beverages 🥤",
    "snack": "Snacks 🍪",
    "condiment": "Condiments 🧂",
    "frozen": "Frozen Food 🧊",
    "egg": "Eggs 🥚",
    "vegetable": "Vegetables 🥦",
    "fruit": "Fruits 🍎",
    "unknown": "Others 📦"
}

# =========================
# 🛠️ Core Functions
# =========================

def scan_image_with_backend(uploaded_file):
    """Upload image to /api/scan and receive AI identification results"""
    api_url = f"{BACKEND_URL}/api/scan"
    
    files = {
        "image": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)
    }
    
    try:
        response = requests.post(api_url, files=files, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            items = result.get("items", [])
            
            cleaned_items = []
            for item in items:
                # Process image path
                img_path = item.get("image")
                if img_path and img_path.startswith("/"):
                    item["image"] = f"{BACKEND_URL}{img_path}"
                
                # Map category to English display
                raw_cat = str(item.get("category", "unknown")).lower()
                item["category"] = CATEGORY_MAP.get(raw_cat, "Others 📦")
                
                cleaned_items.append(item)
                
            return cleaned_items
        else:
            st.error(f"Backend Error: {response.status_code} - {response.text}")
            return []
            
    except requests.exceptions.ConnectionError:
        st.error("Cannot connect to backend! Please ensure `python backend.py` is running.")
        return []
    except Exception as e:
        st.error(f"An unexpected error occurred: {e}")
        return []

# =========================
# 💾 Data Management (JSON)
# =========================
def save_pantry(pantry_list):
    with open(DB_FILE, "w", encoding='utf-8') as f:
        json.dump(pantry_list, f, indent=4, ensure_ascii=False)

def load_pantry():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding='utf-8') as f:
            data = json.load(f)
        
        # Auto-clean items consumed more than 7 days ago
        cleaned_data = []
        today = datetime.now().date()
        dirty = False
        
        for item in data:
            if item.get('status') == 'consumed' and item.get('consumed_at'):
                consumed_date = datetime.strptime(item['consumed_at'], "%Y-%m-%d").date()
                if (today - consumed_date).days > 7:
                    dirty = True
                    continue 
            cleaned_data.append(item)
        
        if dirty: 
            save_pantry(cleaned_data)
        return cleaned_data
    return []

if 'pantry' not in st.session_state:
    st.session_state.pantry = load_pantry()

# =========================
# 🖥️ UI Layout
# =========================

col_logo, col_title = st.columns([1, 5])
with col_title:
    st.title("FRIDDDDGE🧊")

st.divider()

<<<<<<< Updated upstream
# --- 分頁區塊 ---
tab1, tab2, tab3 = st.tabs(["📸 拍照辨識 (AI)", "📝 手動輸入", "Barcode輸入"])
=======
# --- Tabs ---
tab1, tab2, tab3 = st.tabs(["📸 AI Vision", "📝 Manual Entry", "🔍 Barcode Scan"])
>>>>>>> Stashed changes

# [Tab 1] AI Recognition
with tab1:
    st.caption("Take a photo of your food items, and AI will categorize them automatically.")
    
    camera_photo = st.camera_input("Take a photo", label_visibility="collapsed")
    
    if camera_photo:
        col_btn, col_info = st.columns([1, 2])
        
        with col_btn:
            if st.button("🚀 Start Scan", type="primary", use_container_width=True):
                with st.spinner("Analyzing image..."):
                    new_items = scan_image_with_backend(camera_photo)
                    
                    if new_items:
                        st.session_state.pantry.extend(new_items)
                        save_pantry(st.session_state.pantry)
                        st.success(f"Successfully added {len(new_items)} items!")
                        st.rerun()
                    else:
                        st.warning("No items detected. Try moving the camera closer.")

<<<<<<< Updated upstream

# [分頁 2] 手動輸入（升級版）
with tab2:
    st.caption("AI 認不出來也沒關係：手動輸入")

    if "manual_preview" not in st.session_state:
        st.session_state.manual_preview = None

    with st.form("manual_form_v2"):
        col1, col2 = st.columns([2, 1])

        with col1:
            name_in = st.text_input("商品名稱", placeholder="例如：喝剩的牛奶")
            image_in = st.text_input("圖片網址（可選）", placeholder="貼上圖片 URL（例如商品圖片）")

        with col2:
            qty = st.number_input("數量", min_value=1, max_value=50, value=1, step=1)

        cat_in = st.selectbox("分類", list(CATEGORY_MAP.values()))
        date_in = st.date_input("過期日", value=datetime.now().date() + timedelta(days=7))

        # Preview（同一個 form 裡）
        st.markdown("#### ✅ 預覽")
        p1, p2 = st.columns([1, 3])
        with p1:
            if image_in.strip():
                st.image(image_in.strip(), use_container_width=True)
            else:
                st.markdown("<div style='font-size:40px;text-align:center;'>📦</div>", unsafe_allow_html=True)

        with p2:
            st.markdown(f"**{name_in if name_in else '（尚未輸入名稱）'}**")
            st.caption(f"{cat_in} • 到期：{date_in.strftime('%Y-%m-%d')} • 數量：{int(qty)}")

        submitted = st.form_submit_button("➕ 加入冰箱")

    if submitted:
        if not name_in.strip():
            st.warning("請先輸入商品名稱")
        else:
            for _ in range(int(qty)):
                new_item = {
                    "id": str(uuid.uuid4()),
                    "barcode": None,
                    "name": name_in.strip(),
                    "image": image_in.strip() if image_in.strip() else None,
                    "category": cat_in,  # 存中文（跟你的顯示/篩選一致）
=======
# [Tab 2] Manual Entry
with tab2:
    st.caption("Add items manually if AI doesn't recognize them.")
    
    with st.form("manual_form"):
        name_in = st.text_input("Item Name", placeholder="e.g. Whole Milk")
        cat_in = st.selectbox("Category", list(CATEGORY_MAP.values()))
        date_in = st.date_input("Expiry Date", value=datetime.now().date() + timedelta(days=7))
        
        if st.form_submit_button("➕ Add to Fridge"):
            if name_in:
                new_item = {
                    "id": str(uuid.uuid4()),
                    "name": name_in,
                    "image": None,
                    "category": cat_in,
>>>>>>> Stashed changes
                    "added_at": datetime.now().strftime("%Y-%m-%d"),
                    "expire_at": date_in.strftime("%Y-%m-%d"),
                    "status": "in_fridge",
                    "consumed_at": None
                }
                st.session_state.pantry.append(new_item)

            save_pantry(st.session_state.pantry)
            st.success(f"已加入 {int(qty)} 個項目！")
            st.rerun()


# [Tab 3] Barcode Scan
with tab3:
<<<<<<< Updated upstream
    st.caption("輸入商品條碼（Barcode），自動查詢品名與分類後加入冰箱")
=======
    st.caption("Scan or upload a barcode to fetch product information.")

    def scan_barcode_image_with_backend(uploaded_file):
        api_url = f"{BACKEND_URL}/api/scan_barcode"
        files = {"image": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
        try:
            r = requests.post(api_url, files=files, timeout=20)
            if r.status_code == 200:
                return r.json().get("barcodes", [])
            else:
                st.error(f"Barcode identification failed: {r.status_code}")
                return []
        except Exception as e:
            st.error(f"Error: {e}")
            return []
>>>>>>> Stashed changes

    def lookup_barcode_with_backend(barcode: str):
        api_url = f"{BACKEND_URL}/api/barcode/{barcode}"
        try:
            r = requests.get(api_url, timeout=15)
            if r.status_code == 200:
                return r.json().get("item")
<<<<<<< Updated upstream
            else:
                st.error(f"條碼查詢失敗: {r.status_code} - {r.text}")
                return None
        except requests.exceptions.ConnectionError:
            st.error("無法連線到後端！請確認 `python backend.py` 是否正在執行。")
            return None
        except Exception as e:
            st.error(f"發生未預期的錯誤: {e}")
            return None

    # 用 session_state 暫存查詢結果，避免 rerun 後消失
    if "barcode_item" not in st.session_state:
        st.session_state.barcode_item = None

    col_a, col_b = st.columns([2, 1])
    with col_a:
        barcode_in = st.text_input("Barcode", placeholder="例如：0123456789012", label_visibility="visible")
    with col_b:
        qty = st.number_input("數量", min_value=1, max_value=50, value=1, step=1)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔍 查詢條碼", use_container_width=True):
            if barcode_in.strip():
                item = lookup_barcode_with_backend(barcode_in.strip())
                st.session_state.barcode_item = item
            else:
                st.warning("請先輸入條碼")
=======
            return None
        except Exception:
            return None

    if "barcode_candidates" not in st.session_state:
        st.session_state.barcode_candidates = []
    if "barcode_selected" not in st.session_state:
        st.session_state.barcode_selected = ""
    if "barcode_item" not in st.session_state:
        st.session_state.barcode_item = None

    st.markdown("### 1) Take Photo / Upload Barcode")
    col_cam, col_up = st.columns(2)
    with col_cam:
        barcode_photo = st.camera_input("Scan Barcode", label_visibility="collapsed")
    with col_up:
        barcode_upload = st.file_uploader("Upload Image", type=["jpg", "jpeg", "png"], label_visibility="collapsed")

    img_file = barcode_photo or barcode_upload

    if img_file:
        st.image(img_file, use_container_width=True)
        if st.button("🔎 Identify Barcode", type="primary", use_container_width=True):
            with st.spinner("Decoding..."):
                barcodes = scan_barcode_image_with_backend(img_file)
            
            codes = [b.get("data") for b in barcodes if b.get("data")]
            uniq = list(dict.fromkeys(codes))
            st.session_state.barcode_candidates = uniq
            st.session_state.barcode_item = None
            st.session_state.barcode_selected = uniq[0] if uniq else ""
            if not uniq:
                st.warning("No barcode found. Ensure lighting is good and the barcode is horizontal.")
            st.rerun()

    st.markdown("### 2) Select & Lookup")
    if st.session_state.barcode_candidates:
        st.session_state.barcode_selected = st.selectbox(
            "Detected Barcodes",
            st.session_state.barcode_candidates,
            index=0
        )

    manual_code = st.text_input(
        "Barcode Number (Manual Correction)",
        value=st.session_state.barcode_selected or "",
        placeholder="e.g. 0123456789012"
    ).strip()

    if st.button("🌐 Lookup Product Information", use_container_width=True):
        if not manual_code:
            st.warning("Please enter or scan a barcode first.")
        else:
            with st.spinner("Searching database..."):
                item = lookup_barcode_with_backend(manual_code)
            st.session_state.barcode_item = item
            st.session_state.barcode_selected = manual_code
            st.rerun()
>>>>>>> Stashed changes

    item = st.session_state.barcode_item

    if item:
<<<<<<< Updated upstream
        # --- 前端資料清洗（沿用 tab1 的邏輯）---
        # 1) category 英文 -> 中文
        raw_cat = str(item.get("category", "unknown")).lower()
        item_display_cat = CATEGORY_MAP.get(raw_cat, "其他 📦")

        # 2) 顯示預覽
        st.markdown("### ✅ 查詢結果")
=======
        st.markdown("### 3) Confirm & Add")
        raw_cat = str(item.get("category", "unknown")).lower()
        display_cat = CATEGORY_MAP.get(raw_cat, "Others 📦")

>>>>>>> Stashed changes
        cimg, cinfo = st.columns([1, 3])
        with cimg:
            if item.get("image"):
                st.image(item["image"], use_container_width=True)
            else:
                st.markdown("<div style='font-size:40px;text-align:center;'>📦</div>", unsafe_allow_html=True)

        with cinfo:
            st.markdown(f"**{item.get('name', 'unknown')}**")
<<<<<<< Updated upstream
            st.caption(f"分類：{item_display_cat}")
            st.caption(f"建議到期日：{item.get('expire_at')}")

        # 3) 讓使用者可調整分類/到期日（很實用，因為 OFF 分類不一定準）
        st.markdown("### ✍️ 可選：調整資訊再加入")
        edit_col1, edit_col2 = st.columns(2)
        with edit_col1:
            cat_override = st.selectbox("分類（可改）", list(CATEGORY_MAP.values()),
                                        index=list(CATEGORY_MAP.values()).index(item_display_cat) if item_display_cat in CATEGORY_MAP.values() else 0)
        with edit_col2:
            # 預設用後端給的 expire_at
=======
            st.caption(f"Barcode: {item.get('barcode')}")
            st.caption(f"Category: {display_cat}")
            st.caption(f"Suggested Expiry: {item.get('expire_at')}")

        st.markdown("#### Options")
        colA, colB, colC = st.columns([2, 2, 1])
        with colA:
            cat_values = list(CATEGORY_MAP.values())
            default_idx = cat_values.index(display_cat) if display_cat in cat_values else 0
            cat_override = st.selectbox("Edit Category", cat_values, index=default_idx)
        with colB:
>>>>>>> Stashed changes
            try:
                default_exp = datetime.strptime(item.get("expire_at"), "%Y-%m-%d").date()
            except:
                default_exp = datetime.now().date() + timedelta(days=7)
<<<<<<< Updated upstream
            expire_override = st.date_input("到期日（可改）", value=default_exp)

        with col2:
            if st.button("➕ 加入冰箱", type="primary", use_container_width=True):
                # 建立 qty 份 item（與 tab2 schema 對齊）
=======
            expire_override = st.date_input("Edit Expiry", value=default_exp)
        with colC:
            qty = st.number_input("Qty", min_value=1, max_value=50, value=1)

        col_add, col_clear = st.columns(2)
        with col_add:
            if st.button("➕ Add to Fridge", type="primary", use_container_width=True):
>>>>>>> Stashed changes
                for _ in range(int(qty)):
                    st.session_state.pantry.append({
                        "id": str(uuid.uuid4()),
                        "barcode": item.get("barcode"),
                        "name": item.get("name", "unknown"),
<<<<<<< Updated upstream
                        "image": item.get("image"),  # 外部 URL 直接存
                        "category": cat_override,      # 存中文（跟 tab2 一致）
=======
                        "image": item.get("image"),
                        "category": cat_override,
>>>>>>> Stashed changes
                        "added_at": datetime.now().strftime("%Y-%m-%d"),
                        "expire_at": expire_override.strftime("%Y-%m-%d"),
                        "status": "in_fridge",
                        "consumed_at": None
<<<<<<< Updated upstream
                    }

                    st.session_state.pantry.append(new_item)

                save_pantry(st.session_state.pantry)
                st.success(f"已加入 {int(qty)} 個項目！")
                # 清掉暫存避免誤加
                st.session_state.barcode_item = None
                st.rerun()
=======
                    })
                save_pantry(st.session_state.pantry)
                st.success(f"Added {int(qty)} items!")
                st.session_state.barcode_item = None
                st.rerun()
        with col_clear:
            if st.button("🧹 Clear Results", use_container_width=True):
                st.session_state.barcode_item = None
                st.rerun()
    else:
        st.info("Workflow: Photo → Identify → Lookup → Add")
>>>>>>> Stashed changes

st.divider()

# =========================
# ❄️ Fridge Inventory
# =========================
active_items = [item for item in st.session_state.pantry if item.get('status') == 'in_fridge']
categories = ["All"] + sorted(list(set(item.get('category', 'Others 📦') for item in active_items)))

st.subheader(f"❄️ Fridge Inventory ({len(active_items)})")
selected_cat = st.radio("Filter:", categories, horizontal=True, label_visibility="collapsed")

display_items = active_items if selected_cat == "All" else [i for i in active_items if i.get('category') == selected_cat]

if not display_items:
    st.info("The fridge is empty!")

for item in display_items:
    idx = st.session_state.pantry.index(item)
    try:
        expire_obj = datetime.strptime(item['expire_at'], "%Y-%m-%d").date()
        days_left = (expire_obj - datetime.now().date()).days
    except:
        days_left = 0

    with st.container(border=True):
        c1, c2, c3 = st.columns([1.2, 3, 1])
        with c1:
            if item.get('image'):
                st.image(item['image'], width=80, use_container_width=True)
            else:
                st.markdown("<div style='font-size:40px;text-align:center;'>📦</div>", unsafe_allow_html=True)
        with c2:
            st.markdown(f"**{item['name']}**")
            st.caption(f"{item.get('category')} • Expires: {item['expire_at']}")
            if days_left < 0:
                st.markdown(f":red[❌ Expired {abs(days_left)} days ago]")
            elif days_left <= 3:
                st.markdown(f":orange[⚠️ {days_left} days left]")
            else:
                st.markdown(f":green[✅ {days_left} days left]")
        with c3:
            if st.button("🍽️ Eat", key=f"eat_{item['id']}"):
                st.session_state.pantry[idx]['status'] = 'consumed'
                st.session_state.pantry[idx]['consumed_at'] = datetime.now().strftime("%Y-%m-%d")
                save_pantry(st.session_state.pantry)
                st.rerun()

# =========================
# 🗑️ Recently Consumed
# =========================
consumed_items = [item for item in st.session_state.pantry if item.get('status') == 'consumed']

if consumed_items:
    st.markdown("---")
    with st.expander(f"🥣 Recently Consumed ({len(consumed_items)})", expanded=False):
        for item in consumed_items:
            idx = st.session_state.pantry.index(item)
            c1, c2, c3 = st.columns([1, 3, 1.5])
            with c2:
                st.markdown(f"~~{item['name']}~~")
                st.caption(f"Consumed on: {item.get('consumed_at')}")
            with c3:
                col_u, col_d = st.columns(2)
                with col_u:
                    if st.button("↩️", key=f"undo_{item['id']}", help="Back to Fridge"):
                        st.session_state.pantry[idx]['status'] = 'in_fridge'
                        st.session_state.pantry[idx]['consumed_at'] = None
                        save_pantry(st.session_state.pantry)
                        st.rerun()
                with col_d:
                    if st.button("❌", key=f"del_{item['id']}", help="Delete Permanently"):
                        st.session_state.pantry.pop(idx)
                        save_pantry(st.session_state.pantry)
                        st.rerun()
            st.divider()
