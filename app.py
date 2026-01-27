import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
from datetime import datetime
import pandas as pd # 引入數據分析套件
import time # 引入時間套件 (為了重新整理頁面用)

# --- 🎯 設定您的預算上限 (請在這裡修改數字) ---
MONTHLY_WANTS_BUDGET = 3000  # 設定「享樂」類別的每月上限

# --- 設定網頁標題 ---
st.set_page_config(page_title="記帳本", page_icon="💰")

# --- 核心連接功能 (智慧切換版) ---
def connect_to_gsheet():
    scope = [
        'https://spreadsheets.google.com/feeds',
        'https://www.googleapis.com/auth/drive'
    ]

    # --- 第一關：嘗試讀取雲端金庫 (Cloud Secrets) ---
    try:
        if "gcp_service_account" in st.secrets:
            creds_dict = dict(st.secrets["gcp_service_account"])
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            client = gspread.authorize(creds)
            return client
    except Exception:
        pass 

    # --- 第二關：讀取本機檔案 (Local JSON) ---
    base_path = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(base_path, '自動記帳的金鑰.json') 

    if os.path.exists(json_path):
        creds = ServiceAccountCredentials.from_json_keyfile_name(json_path, scope)
        client = gspread.authorize(creds)
        return client
    
    # --- 第三關：都找不到 ---
    st.error("❌ 嚴重錯誤：找不到金鑰！請確認本地有 json 檔，或雲端有設定 Secrets。")
    return None

# --- 介面設計 ---
st.title("💰 我的記帳 APP (操你媽在花錢啊)")

# ===========================
# 🛡️ Level 3：預算哨兵系統 (新增區塊)
# ===========================
client = connect_to_gsheet()
wants_spend = 0 # 預設花費為 0

if client:
    try:
        # 這裡用您設定的試算表名稱
        sheet = client.open("記帳本") 
        target_month = datetime.now().strftime("%Y-%m")
        
        try:
            ws = sheet.worksheet(target_month)
            # 讀取資料來分析
            data = ws.get_all_records()
            
            if data:
                df = pd.DataFrame(data)
                # 確保金額是數字 (處理可能出現的錯誤)
                df['金額'] = pd.to_numeric(df['金額'], errors='coerce').fillna(0)
                
                # 篩選出本月「享樂」的總花費 (配合您的類別名稱)
                wants_spend = df[df['類別'] == '享樂']['金額'].sum()
            else:
                wants_spend = 0
                
        except:
            # 如果這個月還沒開張，花費就是 0
            wants_spend = 0

        # --- 顯示預算儀表板 ---
        st.caption(f"📅 本月「享樂」額度監控 ({target_month})")
        
        remaining = MONTHLY_WANTS_BUDGET - wants_spend
        # 計算進度條 (最大值鎖定在 1.0，避免報錯)
        progress = min(wants_spend / MONTHLY_WANTS_BUDGET, 1.0) 
        
        # 顯示數字
        col_metric1, col_metric2 = st.columns(2)
        col_metric1.metric("已敗家金額", f"${int(wants_spend)}")
        col_metric2.metric("剩餘扣打", f"${int(remaining)}", delta_color="normal" if remaining > 0 else "inverse")

        # 顯示血條 (超過預算變紅色)
        if wants_spend > MONTHLY_WANTS_BUDGET:
            st.error(f"⚠️ 幹！你已經超支 ${int(wants_spend - MONTHLY_WANTS_BUDGET)} 元了！剁手！")
        else:
            st.progress(progress)
            
        st.markdown("---") # 分隔線

    except Exception as e:
        # 剛啟動時可能會連線一下，不顯示錯誤嚇人
        pass
# ===========================

with st.form("entry_form", clear_on_submit=True):
    col1, col2 = st.columns(2)
    with col1:
        date_input = st.date_input("日期", datetime.now())
    with col2:
        # 保留您的自訂類別
        category = st.selectbox("類別", ["生存", "享樂", "投資/儲蓄"])
    
    item = st.text_input("細項說明 (例如：午餐雞腿飯)")
    
    col3, col4 = st.columns(2)
    with col3:
        amount = st.number_input("金額", min_value=1, step=1)
    with col4:
        # 保留您的自訂支付方式 (含乞討)
        payment = st.selectbox("支付方式", ["現金", "信用卡", "行動支付", "轉帳", "乞討"])
    
    note = st.text_area("備註 (選填)")

    # 送出按鈕
    submitted = st.form_submit_button("📤 確認記帳")

    if submitted:
        if not item:
            st.error("❌ 請輸入細項說明！")
        else:
            # 🔥 新增：超支即時警告
            if category == "享樂" and (wants_spend + amount > MONTHLY_WANTS_BUDGET):
                st.toast("⚠️ 警告：這筆花下去就超支囉！", icon="💸")

            status_box = st.empty()
            try:
                status_box.info("🔄 連線中...")
                # 這裡不需要重新連線，直接用上面的 client
                if client:
                    sheet = client.open("記帳本") 
                    
                    target_month = date_input.strftime("%Y-%m")
                    
                    try:
                        ws = sheet.worksheet(target_month)
                    except:
                        ws = sheet.add_worksheet(title=target_month, rows=100, cols=10)
                        ws.append_row(['日期', '類別', '細項說明', '金額', '支付方式', '備註'])
                    
                    row_data = [
                        date_input.strftime("%Y/%m/%d"),
                        category,
                        item,
                        amount,
                        payment,
                        note
                    ]
                    
                    ws.append_row(row_data)
                    status_box.success(f"✅ 記帳成功！ (${amount})")
                    st.balloons()
                    
                    # 🔥 新增：記帳完自動重新整理，讓上面的進度條馬上更新
                    time.sleep(1)
                    st.rerun()
                
            except Exception as e:
                st.error(f"❌ 發生錯誤: {e}")

