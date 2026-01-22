import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
from datetime import datetime
import json

# --- 設定網頁標題 ---
st.set_page_config(page_title="2026 財務指揮中心", page_icon="💰")

# --- 核心連接功能 (智慧切換版) ---
def connect_to_gsheet():
    scope = [
        'https://spreadsheets.google.com/feeds',
        'https://www.googleapis.com/auth/drive'
    ]

    # --- 第一關：嘗試讀取雲端金庫 (Cloud Secrets) ---
    # 我們用 try-except 包起來，這樣就算在本機找不到 secrets 也不會報錯
    try:
        if "gcp_service_account" in st.secrets:
            # 如果在雲端找到密碼，就用雲端的
            creds_dict = dict(st.secrets["gcp_service_account"])
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            client = gspread.authorize(creds)
            return client
    except Exception:
        pass # 如果發生任何錯誤 (例如找不到檔案)，就安靜地跳過，進入下一關

    # --- 第二關：讀取本機檔案 (Local JSON) ---
    # 這是給您在電腦上執行時用的
    base_path = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(base_path, '自動記帳的金鑰.json') # 您的本機檔名

    if os.path.exists(json_path):
        creds = ServiceAccountCredentials.from_json_keyfile_name(json_path, scope)
        client = gspread.authorize(creds)
        return client
    
    # --- 第三關：都找不到 ---
    st.error("❌ 嚴重錯誤：找不到金鑰！請確認本地有 json 檔，或雲端有設定 Secrets。")
    return None

# --- 介面設計 ---
st.title("💰 我的記帳 APP (操你媽在花錢啊)")

with st.form("entry_form", clear_on_submit=True):
    col1, col2 = st.columns(2)
    with col1:
        date_input = st.date_input("日期", datetime.now())
    with col2:
        category = st.selectbox("類別", ["生存 (Needs)", "享樂 (Wants)", "投資/儲蓄 (Future)"])
    
    item = st.text_input("細項說明 (例如：午餐雞腿飯)")
    
    col3, col4 = st.columns(2)
    with col3:
        amount = st.number_input("金額", min_value=1, step=1)
    with col4:
        payment = st.selectbox("支付方式", ["現金", "信用卡", "行動支付", "轉帳"])
    
    note = st.text_area("備註 (選填)")

    # 送出按鈕
    submitted = st.form_submit_button("📤 確認記帳")

    if submitted:
        if not item:
            st.error("❌ 請輸入細項說明！")
        else:
            status_box = st.empty()
            try:
                status_box.info("🔄 連線中...")
                client = connect_to_gsheet()
                
                if client:
                    status_box.info("📂 開啟帳本...")
                    # 請確認您的試算表名稱是 '2026_Financial_Ledger' 或 '記帳本'
                    # 建議您這邊改成您目前真正能用的名稱
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
                
            except Exception as e:

                st.error(f"❌ 發生錯誤: {e}")
