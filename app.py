import streamlit as st
import requests
import json
import os
import uuid
from datetime import datetime, timedelta

# --- 1. 設定頁面 ---
st.set_page_config(page_title="Smart Fridge", page_icon="🥦")

# --- 2. 核心功能函數 ---

def get_product_info(barcode):
    """從 OpenFoodFacts 抓資料"""
    if len(barcode) < 3: return None
    url = f"https://world.openfoodfacts.org/api/v0/product/{barcode}.json"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 1:
                return data['product']
    except Exception as e:
        print(e)
    return None

def determine_category(api_data):
    """自動分類器"""
    if not api_data: return "其他 📦"
    
    categories = str(api_data.get('categories_tags', [])).lower()
    keywords = str(api_data.get('keywords', [])).lower()
    full_text = categories + keywords
    
    if any(x in full_text for x in ['milk', 'dairy', 'cheese', 'yogurt', '乳', '優格']):
        return "乳製品 🥛"
    elif any(x in full_text for x in ['meat', 'chicken', 'beef', 'pork', 'fish', '肉']):
        return "肉類 🥩"
    elif any(x in full_text for x in ['vegetable', 'plant', 'fruit', 'salad', '蔬', '果']):
        return "蔬果 🥦"
    elif any(x in full_text for x in ['beverage', 'drink', 'soda', 'juice', 'water', 'tea', 'coffee', '飲', '茶', '水']):
        return "飲料 🥤"
    elif any(x in full_text for x in ['snack', 'chocolate', 'chip', 'candy', 'cookie', '零食', '餅']):
        return "零食 🍪"
    elif any(x in full_text for x in ['sauce', 'condiment', 'oil', 'vinegar', '醬', '油']):
        return "調味料 🧂"
    elif any(x in full_text for x in ['frozen', 'ice', '凍']):
        return "冷凍食品 🧊"
    else:
        return "一般食品 📦"

def create_pantry_item(api_data, scanned_barcode, user_image=None):
    """建立商品資料"""
    if api_data:
        api_image = api_data.get('image_front_small_url') or api_data.get('image_front_url')
        item_name = api_data.get('product_name', '未知商品')
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
        "status": "in_fridge", # 初始狀態
        "consumed_at": None      # 尚未完食
    }

# --- 3. 資料庫管理 & 自動清理邏輯 ---
DB_FILE = "pantry.json"

def save_pantry(pantry_list):
    with open(DB_FILE, "w") as f:
        json.dump(pantry_list, f, indent=4)

def load_pantry():
    """載入資料並執行自動清理 (Auto-Delete 7天後的完食項目)"""
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            data = json.load(f)
            
        # --- 自動清理邏輯 ---
        cleaned_data = []
        today = datetime.now().date()
        dirty = False # 標記是否有資料被刪除，若有才存檔

        for item in data:
            # 如果是「已完食」，檢查是否超過 7 天
            if item.get('status') == 'consumed' and item.get('consumed_at'):
                consumed_date = datetime.strptime(item['consumed_at'], "%Y-%m-%d").date()
                days_passed = (today - consumed_date).days
                if days_passed > 7:
                    dirty = True
                    continue # 跳過這個項目 (等於刪除)
            
            cleaned_data.append(item)
        
        if dirty:
            save_pantry(cleaned_data)
            
        return cleaned_data
    return []

if 'pantry' not in st.session_state:
    st.session_state.pantry = load_pantry()

# --- 4. 跳出視窗 ---
@st.dialog("📝 手動新增食材")
def manual_entry_dialog():
    st.caption("適用於：剩菜、無條碼商品")
    name_input = st.text_input("商品名稱", placeholder="例如：媽媽煮的滷肉")
    category_options = ["一般食品 📦", "乳製品 🥛", "肉類 🥩", "蔬果 🥦", "飲料 🥤", "零食 🍪", "調味料 🧂", "冷凍食品 🧊", "熟食 🍲"]
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
                "consumed_at": None
            }
            st.session_state.pantry.append(new_item)
            save_pantry(st.session_state.pantry)
            st.success(f"已加入：{name_input}")
            st.rerun()
        else:
            st.warning("請輸入名稱")

# ================= UI 介面開始 =================

# --- 標題區塊 ---
col_logo, col_title = st.columns([1, 5])
with col_logo:
    if os.path.exists("fridge_icon.png"):
        st.image("fridge_icon.png", width=60)
    else:
        st.write("🥦") 
with col_title:
    st.title("智慧冰箱")

st.write("---")

# --- 輸入區塊 ---
col_tabs, col_manual_btn = st.columns([3, 1])
with col_manual_btn:
    st.write("") 
    if st.button("➕ 手動輸入"):
        manual_entry_dialog()

with col_tabs:
    tab1, tab2 = st.tabs(["📸 拍照掃描", "⌨️ Barcode 輸入"])

    with tab1:
        camera_photo = st.camera_input("點擊拍照", key="camera_scan", label_visibility="collapsed")
        if camera_photo:
            st.success("影像已擷取！")
            simulated_code = st.text_input("辨識結果", value="3017620422003", key="cam_code")
            if st.button("加入", key="btn_cam_add"):
                raw_product = get_product_info(simulated_code)
                new_item = create_pantry_item(raw_product, simulated_code)
                st.session_state.pantry.append(new_item)
                save_pantry(st.session_state.pantry)
                st.rerun()

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

# ================= 📦 主要清單 (冰箱中) =================

# 1. 篩選資料：只顯示「在冰箱中」的
active_items = [item for item in st.session_state.pantry if item.get('status') == 'in_fridge']

# 2. 分類篩選器
all_categories = ["全部"] + sorted(list(set(item.get('category', '其他 📦') for item in active_items)))

st.subheader("❄️ 我的冰箱")
selected_category = st.radio(
    "篩選分類：", 
    all_categories, 
    horizontal=True,
    label_visibility="collapsed"
)

if selected_category == "全部":
    filtered_pantry = active_items
else:
    filtered_pantry = [item for item in active_items if item.get('category') == selected_category]

st.caption(f"目前顯示: {selected_category} ({len(filtered_pantry)} 項)")

if not filtered_pantry and selected_category != "全部":
    st.info(f"你的冰箱裡沒有 {selected_category} 喔！")

for index, item in enumerate(filtered_pantry):
    
    original_index = st.session_state.pantry.index(item)
    expire_date = datetime.strptime(item['expire_at'], "%Y-%m-%d").date()
    days_left = (expire_date - datetime.now().date()).days
    item_category = item.get('category', '一般 📦')

    # 使用 container 包起來
    with st.container(border=True):
        # 調整比例：左邊縮圖(1.5) 中間資訊(3.5) 右邊按鈕(1)
        # 這樣在某些寬一點的手機上比較有機會維持橫向排列
        c1, c2, c3 = st.columns([1.5, 3.5, 1])
        
        with c1:
            # [修正] 這裡改成 width=80，確保它永遠是小縮圖
            if item['image'] and item['image'].startswith("http"):
                st.image(item['image'], width=80)
            else:
                # 讓 Emoji 也置中顯示大一點
                st.markdown("<div style='text-align: center; font-size: 40px;'>📦</div>", unsafe_allow_html=True)

        with c2:
            st.markdown(f"**{item['name']}**")
            st.caption(f"{item_category} • {item['expire_at']}")
            
            # 使用更精簡的 Badge 顯示天數
            if days_left < 3:
                st.markdown(f":red[⚠️ 剩 {days_left} 天]")
            else:
                st.markdown(f":green[✅ 剩 {days_left} 天]")

        with c3:
            # 把按鈕垂直置中 (透過塞空白行)
            st.write("")
            st.write("")
            if st.button("🍽️", key=f"eat_{item['id']}"):
                st.session_state.pantry[original_index]['status'] = 'consumed'
                st.session_state.pantry[original_index]['consumed_at'] = datetime.now().strftime("%Y-%m-%d")
                save_pantry(st.session_state.pantry)
                st.rerun()

# ================= 🗑️ 近期已完食 (Recently Consumed) =================

# 篩選出「已完食」的項目
consumed_items = [item for item in st.session_state.pantry if item.get('status') == 'consumed']

if consumed_items:
    st.markdown("---")
    st.subheader(f"🥣 近期已完食 ({len(consumed_items)})")
    st.caption("這裡會保留 7 天，或是你可以手動刪除。")

    for item in consumed_items:
        original_index = st.session_state.pantry.index(item)
        
        with st.container(): # 使用簡單的容器，不加邊框，顯示為灰色感覺
            col_a, col_b, col_c = st.columns([1, 3, 1])
            
            with col_a:
                # 圖片變小一點或黑白 (這裡先維持原樣)
                if item['image'] and item['image'].startswith("http"):
                    st.image(item['image'], width=40)
                else:
                    st.write("🥣")
            
            with col_b:
                st.write(f"~~{item['name']}~~") # 加上刪除線
                st.caption(f"完食於: {item.get('consumed_at')}")
                
            with col_c:
                # 1. 復原按鈕 (Undo)
                if st.button("↩️", key=f"restore_{item['id']}", help="放回冰箱"):
                    st.session_state.pantry[original_index]['status'] = 'in_fridge'
                    st.session_state.pantry[original_index]['consumed_at'] = None
                    save_pantry(st.session_state.pantry)
                    st.rerun()
                
                # 2. 永久刪除按鈕
                if st.button("❌", key=f"del_{item['id']}", help="永久刪除"):
                    st.session_state.pantry.pop(original_index)
                    save_pantry(st.session_state.pantry)
                    st.rerun()
            
            st.divider() # 分隔線