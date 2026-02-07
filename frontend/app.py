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
# BACKEND_URL = "http://127.0.0.1:8000"
BACKEND_URL = "https://tartonhack.onrender.com/"

# Streamlit Page Configuration
st.set_page_config(
    page_title="SCOTTY FRIDDDDDGE", 
    page_icon="frontend/scotty.png"  
)

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
# 🖥️ UI Layout (Header 修飾版)
# =========================
# 改成 [0.8, 5] 讓 logo 不要離標題太遠
col_logo, col_title = st.columns([0.8, 4], gap="medium", vertical_alignment="center")

with col_logo:
    try:
        # 加上 width 限制，避免它無限放大
        st.image("frontend/scotty.png", width=80) 
    except:
        st.write("🐶") 

with col_title:
    st.title("SCOTTY FRIDDDDDGE 🧊")
    st.caption("Remember what you've bought!") # 用 caption 取代 markdown 比較秀氣

st.divider()

# --- Tabs ---
tab1, tab2, tab3 = st.tabs(["📸 AI Vision", "📝 Manual Entry", "🔍 Barcode Scan"])

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
                    "added_at": datetime.now().strftime("%Y-%m-%d"),
                    "expire_at": date_in.strftime("%Y-%m-%d"),
                    "status": "in_fridge",
                    "consumed_at": None
                }
                st.session_state.pantry.append(new_item)
                save_pantry(st.session_state.pantry)
                st.rerun()

# [Tab 3] Barcode Scan
with tab3:
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

    def lookup_barcode_with_backend(barcode: str):
        api_url = f"{BACKEND_URL}/api/barcode/{barcode}"
        try:
            r = requests.get(api_url, timeout=15)
            if r.status_code == 200:
                return r.json().get("item")
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

    item = st.session_state.barcode_item
    if item:
        st.markdown("### 3) Confirm & Add")
        
        # ==========================================
        # 🚨 補回這兩行！不然下面 display_cat 會報錯
        # ==========================================
        raw_cat = str(item.get("category", "unknown")).lower()
        display_cat = CATEGORY_MAP.get(raw_cat, "Others 📦")
        # ==========================================

        # --- 佈局 ---
        cimg, cinfo = st.columns([1, 2])
        
        with cimg:
            if item.get("image"):
                st.image(item["image"], use_container_width=True)
            else:
                st.markdown("📦")

        with cinfo:
            st.markdown(f"### {item.get('name', 'unknown')}")
            st.caption(f"Barcode: {item.get('barcode')}")
            # 這裡也可以顯示一下分類
            st.caption(f"Category: {display_cat}") 
            
            # ==========================
            # 🧪 Bio-Scanner Feature 
            # ==========================
            st.markdown("---")
            st.markdown("**🧬 Bio-Analysis:**")

            # 1. NOVA Group
            nova = item.get("nova_group")
            if nova == 4:
                st.error("⚠️ **ULTRA-PROCESSED (NOVA 4)**")
                st.caption("Contains industrial formulations.")
            elif nova == 3:
                st.warning("⚠️ Processed Food (NOVA 3)")
            elif nova == 1:
                st.success("✅ Unprocessed / Minimally Processed")
            else:
                st.info(f"Processing Level: {nova if nova else 'Unknown'}")

            # 2. Sugar
            sugar_content = item.get("sugar_100g", 0)
            if sugar_content:
                # 這裡加個防呆，有些資料是字串
                try:
                    sugar_val = float(sugar_content)
                except:
                    sugar_val = 0
                
                cubes = int(sugar_val / 3)
                if cubes > 0:
                    st.write(f"**Sugar:** {sugar_val}g / 100g")
                    st.markdown(f"{'🍬' * cubes}")
                else:
                    st.caption("✅ Low Sugar / Sugar Free")

        # ==========================
        # Options (這裡就不會報錯了)
        # ==========================
        st.markdown("#### Options")
        colA, colB, colC = st.columns([2, 2, 1])
        with colA:
            cat_values = list(CATEGORY_MAP.values())
            # 現在 display_cat 已經定義了，這裡就安全了
            default_idx = cat_values.index(display_cat) if display_cat in cat_values else 0
            cat_override = st.selectbox("Edit Category", cat_values, index=default_idx)
            
        # ... (後面的 Expiry 和 Qty 保持不變) ...
        with colB:
            try:
                default_exp = datetime.strptime(item.get("expire_at"), "%Y-%m-%d").date()
            except:
                default_exp = datetime.now().date() + timedelta(days=7)
            expire_override = st.date_input("Edit Expiry", value=default_exp)
        with colC:
            qty = st.number_input("Qty", min_value=1, max_value=50, value=1)

        col_add, col_clear = st.columns(2)
        with col_add:
            if st.button("➕ Add to Fridge", type="primary", use_container_width=True):
                for _ in range(int(qty)):
                    st.session_state.pantry.append({
                        "id": str(uuid.uuid4()),
                        "barcode": item.get("barcode"),
                        "name": item.get("name", "unknown"),
                        "image": item.get("image"),
                        "category": cat_override,
                        "added_at": datetime.now().strftime("%Y-%m-%d"),
                        "expire_at": expire_override.strftime("%Y-%m-%d"),
                        "nova_group": item.get("nova_group"),
                        "sugar_100g": item.get("sugar_100g"),
                        "status": "in_fridge",
                        "consumed_at": None
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

# ==========================================
# 📐 Compact UI (緊湊版清單)
# ==========================================

for item in display_items:
    idx = st.session_state.pantry.index(item)
    
    # 計算過期天數
    try:
        expire_obj = datetime.strptime(item['expire_at'], "%Y-%m-%d").date()
        days_left = (expire_obj - datetime.now().date()).days
    except:
        days_left = 0

    with st.container(border=True):
        # 調整欄位比例：[0.5] 是給小圖片，[3] 給文字，[0.8] 給按鈕
        c1, c2, c3 = st.columns([0.5, 3, 0.8])
        
        # --- 1. 小圖片 (Thumbnail) ---
        with c1:
            if item.get('image'):
                st.image(item['image'], width=60) # 👈 改成 60，變更精緻
            else:
                st.markdown("📦")
        
        # --- 2. 資訊區 (濃縮版) ---
        with c2:
            # 第一行：品名 + 分類 (用 bold 顯示品名)
            st.markdown(f"**{item['name']}** <span style='color:gray; font-size:0.8em'>({item.get('category')})</span>", unsafe_allow_html=True)
            
            # --- 準備標籤 (Tags) ---
            tags = []
            
            # (A) 過期狀態 (用簡寫)
            if days_left < 0:
                tags.append(f":red[❌ {abs(days_left)}d ago]")
            elif days_left <= 3:
                tags.append(f":orange[⚠️ {days_left}d left]")
            else:
                tags.append(f":green[✅ {days_left}d]")

            # (B) NOVA 加工等級
            nova = item.get("nova_group")
            if nova == 4:
                tags.append(":red[☣️ Processed]")
            elif nova == 1:
                tags.append(":green[🌿 Natural]")

            # (C) 糖分
            sugar = item.get("sugar_100g")
            if sugar and float(sugar) > 10:
                tags.append(f":red[🍬 {int(float(sugar))}g / 100g  Sug]")

            # 第二行：把所有標籤用 ' • ' 串起來，只佔一行
            st.caption(" • ".join(tags))

        # --- 3. 按鈕區 (垂直置中) ---
        with c3:
            # 這裡用一個 trick 讓按鈕在容器裡看起來比較置中
            st.write("") 
            if st.button("🍽️", key=f"eat_{item['id']}", help="Eat this!", use_container_width=True):
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
