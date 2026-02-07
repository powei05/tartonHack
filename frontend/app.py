import streamlit as st
import requests
import json
import os
import uuid
from datetime import datetime, timedelta

# =========================
# 🔧 設定與常數
# =========================
# 後端 API 地址 (請確認你的 FastAPI 有跑在 port 8000)
BACKEND_URL = "http://127.0.0.1:8000"

# 讓 Streamlit 頁面設定
st.set_page_config(page_title="Smart Fridge", page_icon="🥦")

# 本地資料庫檔案
DB_FILE = "pantry.json"

# --- 分類對照表 (後端英文 -> 前端中文) ---
# 這樣你的模型只要回傳 "eggs"，介面就會顯示 "蛋類 🥚"
CATEGORY_MAP = {
    # 標準類別
    "eggs": "蛋類 🥚",
    "vegetables": "蔬果 🥦",
    "fruits": "蔬果 🍎",
    "dairy": "乳製品 🥛",
    "meat": "肉類 🥩",
    "beverage": "飲料 🥤",
    "snack": "零食 🍪",
    "condiment": "調味料 🧂",
    "frozen": "冷凍食品 🧊",
    # 容錯處理 (大小寫或複數)
    "egg": "蛋類 🥚",
    "vegetable": "蔬果 🥦",
    "fruit": "蔬果 🍎",
    "unknown": "其他 📦"
}

# =========================
# 🛠️ 核心功能函數
# =========================

def scan_image_with_backend(uploaded_file):
    """
    將圖片上傳到後端 /api/scan，並接收模型辨識結果
    """
    api_url = f"{BACKEND_URL}/api/scan"
    
    # 準備檔案格式
    files = {
        "image": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)
    }
    
    try:
        response = requests.post(api_url, files=files, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            items = result.get("items", [])
            
            # --- 資料清洗 ---
            cleaned_items = []
            for item in items:
                # 1. 處理圖片路徑: 把 /uploads/xxx.jpg 變成 http://localhost:8000/uploads/xxx.jpg
                img_path = item.get("image")
                if img_path and img_path.startswith("/"):
                    item["image"] = f"{BACKEND_URL}{img_path}"
                
                # 2. 處理分類: 英文 -> 中文
                raw_cat = str(item.get("category", "unknown")).lower()
                item["category"] = CATEGORY_MAP.get(raw_cat, "其他 📦")
                
                cleaned_items.append(item)
                
            return cleaned_items
        else:
            st.error(f"後端錯誤: {response.status_code} - {response.text}")
            return []
            
    except requests.exceptions.ConnectionError:
        st.error("無法連線到後端！請確認 `python backend.py` 是否正在執行。")
        return []
    except Exception as e:
        st.error(f"發生未預期的錯誤: {e}")
        return []

# =========================
# 💾 資料庫 (JSON) 管理
# =========================
def save_pantry(pantry_list):
    with open(DB_FILE, "w", encoding='utf-8') as f:
        json.dump(pantry_list, f, indent=4, ensure_ascii=False)

def load_pantry():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding='utf-8') as f:
            data = json.load(f)
        
        # 自動清理超過 7 天的完食項目
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
# 🖥️ UI 介面
# =========================

col_logo, col_title = st.columns([1, 5])
#with col_logo:
#    st.write("🥦")
with col_title:
    st.title("FOOOOOOD in FRIDDDDDDGE")

st.divider()

# --- 分頁區塊 ---
tab1, tab2, tab3 = st.tabs(["📸 拍照辨識 (AI)", "📝 手動輸入", "掃描/輸入條碼"])

# [分頁 1] 拍照辨識
with tab1:
    st.caption("拍攝冰箱內的食材，讓 AI 自動幫你分類")
    
    camera_photo = st.camera_input("請拍照", label_visibility="collapsed")
    
    if camera_photo:
        # 當使用者拍下照片後
        col_btn, col_info = st.columns([1, 2])
        
        with col_btn:
            if st.button("🚀 開始辨識", type="primary", use_container_width=True):
                with st.spinner("正在傳送給 AI 模型分析..."):
                    # 呼叫後端 API
                    new_items = scan_image_with_backend(camera_photo)
                    
                    if new_items:
                        st.session_state.pantry.extend(new_items)
                        save_pantry(st.session_state.pantry)
                        st.success(f"成功辨識並加入 {len(new_items)} 個項目！")
                        st.rerun()
                    else:
                        st.warning("模型沒有偵測到任何食物，請試著靠近一點拍攝。")

# [分頁 2] 手動輸入 (保留原本功能)
with tab2:
    st.caption("如果 AI 認不出來，也可以手動輸入")
    
    with st.form("manual_form"):
        name_in = st.text_input("商品名稱", placeholder="例如：喝剩的牛奶")
        cat_in = st.selectbox("分類", list(CATEGORY_MAP.values()))
        date_in = st.date_input("過期日", value=datetime.now().date() + timedelta(days=7))
        
        if st.form_submit_button("➕ 加入冰箱"):
            if name_in:
                new_item = {
                    "id": str(uuid.uuid4()),
                    "name": name_in,
                    "image": None,
                    "category": cat_in, # 直接存中文
                    "added_at": datetime.now().strftime("%Y-%m-%d"),
                    "expire_at": date_in.strftime("%Y-%m-%d"),
                    "status": "in_fridge",
                    "consumed_at": None
                }
                st.session_state.pantry.append(new_item)
                save_pantry(st.session_state.pantry)
                st.rerun()

with tab3:
    st.caption("拍攝或上傳條碼照片，系統會自動讀取 Barcode 並查詢商品資訊")

    # -------------------------
    # helpers
    # -------------------------
    def scan_barcode_image_with_backend(uploaded_file):
        """把條碼照片丟給後端 /api/scan_barcode 解碼"""
        api_url = f"{BACKEND_URL}/api/scan_barcode"
        files = {"image": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
        try:
            r = requests.post(api_url, files=files, timeout=20)
            if r.status_code == 200:
                return r.json().get("barcodes", [])
            else:
                st.error(f"條碼辨識失敗: {r.status_code} - {r.text}")
                return []
        except requests.exceptions.ConnectionError:
            st.error("無法連線到後端！請確認後端正在執行。")
            return []
        except Exception as e:
            st.error(f"發生未預期錯誤: {e}")
            return []

    def lookup_barcode_with_backend(barcode: str):
        """用條碼去後端 /api/barcode/{code} 查 OpenFoodFacts，拿回 item"""
        api_url = f"{BACKEND_URL}/api/barcode/{barcode}"
        try:
            r = requests.get(api_url, timeout=15)
            if r.status_code == 200:
                return r.json().get("item")
            else:
                st.error(f"條碼查詢失敗: {r.status_code} - {r.text}")
                return None
        except requests.exceptions.ConnectionError:
            st.error("無法連線到後端！請確認後端正在執行。")
            return None
        except Exception as e:
            st.error(f"發生未預期錯誤: {e}")
            return None

    # -------------------------
    # session state
    # -------------------------
    if "barcode_candidates" not in st.session_state:
        st.session_state.barcode_candidates = []  # list of decoded codes
    if "barcode_selected" not in st.session_state:
        st.session_state.barcode_selected = ""
    if "barcode_item" not in st.session_state:
        st.session_state.barcode_item = None

    # -------------------------
    # UI: input image
    # -------------------------
    st.markdown("### 1) 拍條碼 / 上傳條碼照片")

    col_cam, col_up = st.columns(2)
    with col_cam:
        barcode_photo = st.camera_input("用相機拍條碼", label_visibility="collapsed")
    with col_up:
        barcode_upload = st.file_uploader("或上傳圖片", type=["jpg", "jpeg", "png"], label_visibility="collapsed")

    img_file = barcode_photo or barcode_upload

    if img_file:
        st.image(img_file, use_container_width=True)

        col_btn1, col_btn2 = st.columns([1, 2])
        with col_btn1:
            if st.button("🔎 辨識條碼", type="primary", use_container_width=True):
                with st.spinner("正在辨識條碼..."):
                    barcodes = scan_barcode_image_with_backend(img_file)

                # 抽出 data
                codes = [b.get("data") for b in barcodes if b.get("data")]
                # 去重保序
                seen = set()
                uniq = []
                for c in codes:
                    if c not in seen:
                        seen.add(c)
                        uniq.append(c)

                st.session_state.barcode_candidates = uniq
                st.session_state.barcode_item = None
                st.session_state.barcode_selected = uniq[0] if uniq else ""
                if not uniq:
                    st.warning("沒有讀到條碼。建議：靠近一點、避免反光、讓條碼水平清楚入鏡。")
                st.rerun()

    st.markdown("### 2) 選擇條碼 / 手動輸入")

    # 如果辨識到多個條碼，讓使用者挑
    if st.session_state.barcode_candidates:
        st.session_state.barcode_selected = st.selectbox(
            "辨識到的條碼（可選）",
            st.session_state.barcode_candidates,
            index=st.session_state.barcode_candidates.index(st.session_state.barcode_selected)
            if st.session_state.barcode_selected in st.session_state.barcode_candidates
            else 0
        )

    # 也允許手動輸入/修正
    manual_code = st.text_input(
        "條碼（可手動貼上/修正）",
        value=st.session_state.barcode_selected or "",
        placeholder="例如：0123456789012"
    ).strip()

    colq1, colq2 = st.columns([1, 2])
    with colq1:
        if st.button("🌐 查詢商品", use_container_width=True):
            if not manual_code:
                st.warning("請先輸入或辨識出條碼")
            else:
                with st.spinner("正在查詢商品資訊..."):
                    item = lookup_barcode_with_backend(manual_code)
                st.session_state.barcode_item = item
                st.session_state.barcode_selected = manual_code
                st.rerun()

    # -------------------------
    # UI: show item + add
    # -------------------------
    item = st.session_state.barcode_item
    if item:
        st.markdown("### 3) 確認資訊並加入冰箱")

        # category 英文 -> 中文（對齊你的 UI）
        raw_cat = str(item.get("category", "unknown")).lower()
        display_cat = CATEGORY_MAP.get(raw_cat, "其他 📦")

        # preview
        cimg, cinfo = st.columns([1, 3])
        with cimg:
            if item.get("image"):
                st.image(item["image"], use_container_width=True)
            else:
                st.markdown("<div style='font-size:40px;text-align:center;'>📦</div>", unsafe_allow_html=True)

        with cinfo:
            st.markdown(f"**{item.get('name', 'unknown')}**")
            st.caption(f"Barcode: {item.get('barcode')}")
            st.caption(f"分類：{display_cat}")
            st.caption(f"建議到期日：{item.get('expire_at')}")

        # allow overrides
        st.markdown("#### 可選：調整後再加入")

        colA, colB, colC = st.columns([2, 2, 1])
        with colA:
            cat_values = list(CATEGORY_MAP.values())
            # default select to display_cat
            default_idx = cat_values.index(display_cat) if display_cat in cat_values else 0
            cat_override = st.selectbox("分類（可改）", cat_values, index=default_idx)

        with colB:
            try:
                default_exp = datetime.strptime(item.get("expire_at"), "%Y-%m-%d").date()
            except:
                default_exp = datetime.now().date() + timedelta(days=7)
            expire_override = st.date_input("到期日（可改）", value=default_exp)

        with colC:
            qty = st.number_input("數量", min_value=1, max_value=50, value=1, step=1)

        col_add, col_clear = st.columns(2)
        with col_add:
            if st.button("➕ 加入冰箱", type="primary", use_container_width=True):
                for _ in range(int(qty)):
                    new_item = {
                        "id": str(uuid.uuid4()),
                        "barcode": item.get("barcode"),
                        "name": item.get("name", "unknown"),
                        "image": item.get("image"),
                        "category": cat_override,  # 存中文（跟 tab2 一致）
                        "added_at": datetime.now().strftime("%Y-%m-%d"),
                        "expire_at": expire_override.strftime("%Y-%m-%d"),
                        "status": "in_fridge",
                        "consumed_at": None
                    }
                    st.session_state.pantry.append(new_item)

                save_pantry(st.session_state.pantry)
                st.success(f"成功加入 {int(qty)} 個！")

                # reset
                st.session_state.barcode_item = None
                st.session_state.barcode_candidates = []
                st.session_state.barcode_selected = ""
                st.rerun()

        with col_clear:
            if st.button("🧹 清除結果", use_container_width=True):
                st.session_state.barcode_item = None
                st.session_state.barcode_candidates = []
                st.session_state.barcode_selected = ""
                st.rerun()

    else:
        st.info("流程：拍/上傳條碼 → 辨識條碼 → 查詢商品 → 加入冰箱")


st.divider()

# =========================
# ❄️ 冰箱清單顯示區
# =========================

active_items = [item for item in st.session_state.pantry if item.get('status') == 'in_fridge']
categories = ["全部"] + sorted(list(set(item.get('category', '其他 📦') for item in active_items)))

st.subheader(f"❄️ 冰箱庫存 ({len(active_items)})")
selected_cat = st.radio("篩選：", categories, horizontal=True, label_visibility="collapsed")

# 篩選邏輯
display_items = active_items if selected_cat == "全部" else [i for i in active_items if i.get('category') == selected_cat]

if not display_items:
    st.info("這裡空空如也～")

for item in display_items:
    idx = st.session_state.pantry.index(item)
    
    # 計算剩餘天數
    try:
        expire_obj = datetime.strptime(item['expire_at'], "%Y-%m-%d").date()
        days_left = (expire_obj - datetime.now().date()).days
    except:
        days_left = 0

    with st.container(border=True):
        c1, c2, c3 = st.columns([1.2, 3, 1])
        
        with c1:
            # 圖片顯示邏輯
            if item.get('image'):
                st.image(item['image'], width=80, use_container_width=True)
            else:
                st.markdown("<div style='font-size:40px;text-align:center;'>📦</div>", unsafe_allow_html=True)
        
        with c2:
            st.markdown(f"**{item['name']}**")
            st.caption(f"{item.get('category')} • 到期：{item['expire_at']}")
            
            if days_left < 0:
                st.markdown(f":red[❌ 已過期 {abs(days_left)} 天]")
            elif days_left <= 3:
                st.markdown(f":orange[⚠️ 剩 {days_left} 天]")
            else:
                st.markdown(f":green[✅ 剩 {days_left} 天]")
                
        with c3:
            st.write("")
            if st.button("🍽️ 吃掉", key=f"eat_{item['id']}"):
                st.session_state.pantry[idx]['status'] = 'consumed'
                st.session_state.pantry[idx]['consumed_at'] = datetime.now().strftime("%Y-%m-%d")
                save_pantry(st.session_state.pantry)
                st.rerun()

# =========================
# 🗑️ 近期已完食
# =========================
consumed_items = [item for item in st.session_state.pantry if item.get('status') == 'consumed']

if consumed_items:
    st.markdown("---")
    with st.expander(f"🥣 近期已完食 ({len(consumed_items)})", expanded=False):
        for item in consumed_items:
            idx = st.session_state.pantry.index(item)
            c1, c2, c3 = st.columns([1, 3, 1.5])
            
            with c2:
                st.markdown(f"~~{item['name']}~~")
                st.caption(f"完食於: {item.get('consumed_at')}")
            
            with c3:
                col_u, col_d = st.columns(2)
                with col_u:
                    if st.button("↩️", key=f"undo_{item['id']}", help="放回冰箱"):
                        st.session_state.pantry[idx]['status'] = 'in_fridge'
                        st.session_state.pantry[idx]['consumed_at'] = None
                        save_pantry(st.session_state.pantry)
                        st.rerun()
                with col_d:
                    if st.button("❌", key=f"del_{item['id']}", help="永久刪除"):
                        st.session_state.pantry.pop(idx)
                        save_pantry(st.session_state.pantry)
                        st.rerun()
            st.divider()
