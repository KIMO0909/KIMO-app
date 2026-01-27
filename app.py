import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
from datetime import datetime
import pandas as pd
import time

# ==========================================
# 🎯 預算設定區 (請在這裡修改您的金額)
# ==========================================
BUDGET_CONFIG = {
    "生存": 6000,       # 吃飯、交通
    "享樂": 3000,       # 網購、玩樂
    "投資/儲蓄": 1000   # 存錢
}
TOTAL_BUDGET = 10000    # 月總預算
# ==========================================

# --- 設定網頁標題 ---
st.set_page_config(page_title="KIMO專屬記帳本", page_icon="💰")

# --- 核心連接功能 ---
def connect_to_gsheet():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    try:
        if "gcp_service_account" in st.secrets:
            creds_dict = dict(st.secrets["gcp_service_account"])
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            client = gspread.authorize(creds)
            return client
    except Exception:
        pass 
    
    base_path = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(base_path, '自動記帳的金鑰.json')
    if os.path.exists(json_path):
        creds = ServiceAccountCredentials.from_json_keyfile_name(json_path, scope)
        client = gspread.authorize(creds)
        return client
    return None

st.title("💰 我的記帳 APP (預算全監控版)")

# ===========================
# 🛡️ Level 4：全方位預算儀表板
# ===========================
client = connect_to_gsheet()
current_spends = {"生存": 0, "享樂": 0, "投資/儲蓄": 0}
total_spend = 0

if client:
    try:
        sheet = client.open("記帳本")
        target_month = datetime.now().strftime("%Y-%m")
        
        try:
            ws = sheet.worksheet(target_month)
            data = ws.get_all_records()
            
            if data:
                df = pd.DataFrame(data)
                df['金額'] = pd.to_numeric(df['金額'], errors='coerce').fillna(0)
                
                # 計算各分類花費
                for category in BUDGET_CONFIG.keys():
                    current_spends[category] = df[df['類別'] == category]['金額'].sum()
                
                # 計算總花費
                total_spend = df['金額'].sum()
        except:
            pass # 新月份無資料

        # --- 1. 總預算大血條 ---
        st.subheader(f"📅 本月總支出監控 ({target_month})")
        total_remain = TOTAL_BUDGET - total_spend
        total_progress = min(total_spend / TOTAL_BUDGET, 1.0)
        
        c1, c2, c3 = st.columns(3)
        c1.metric("總預算", f"${TOTAL_BUDGET}")
        c2.metric("目前總花費", f"${int(total_spend)}")
        c3.metric("剩餘可花", f"${int(total_remain)}", delta_color="normal" if total_remain > 0 else "inverse")
        
        if total_spend > TOTAL_BUDGET:
            st.error(f"🔥 警告！總預算已爆表！超支 ${int(total_spend - TOTAL_BUDGET)}")
        else:
            st.progress(total_progress)

        st.markdown("---")

        # --- 2. 各分類小儀表 ---
        st.caption("📊 各類別預算詳情")
        cols = st.columns(3)
        
        # 依照順序顯示：生存 -> 享樂 -> 投資
        for idx, (cat, budget) in enumerate(BUDGET_CONFIG.items()):
            spend = current_spends[cat]
            remain = budget - spend
            
            with cols[idx]:
                st.write(f"**{cat}**")
                st.write(f"限額: ${budget}")
                # 顯示進度條 (如果爆了變紅色文字，沒爆顯示進度條)
                if spend > budget:
                    st.markdown(f":red[⚠️ 已超支 ${int(spend - budget)}]")
                else:
                    st.progress(min(spend/budget, 1.0) if budget > 0 else 0)
                    st.caption(f"剩 ${int(remain)}")

        st.markdown("---")

    except Exception as e:
        pass

# ===========================
# 📝 記帳輸入區
# ===========================
with st.form("entry_form", clear_on_submit=True):
    col1, col2 = st.columns(2)
    with col1:
        date_input = st.date_input("日期", datetime.now())
    with col2:
        category = st.selectbox("類別", list(BUDGET_CONFIG.keys())) # 自動抓取設定的類別
    
    item = st.text_input("細項說明")
    
    col3, col4 = st.columns(2)
    with col3:
        amount = st.number_input("金額", min_value=1, step=1)
    with col4:
        payment = st.selectbox("支付方式", ["現金", "信用卡", "行動支付", "轉帳", "乞討"])
    
    note = st.text_area("備註 (選填)")

    submitted = st.form_submit_button("📤 確認記帳")

    if submitted:
        if not item:
            st.error("❌ 請輸入細項說明！")
        else:
            # 🔥 智慧防爆檢查
            warning_msg = []
            
            # 1. 檢查該類別是否會爆
            if (current_spends[category] + amount) > BUDGET_CONFIG[category]:
                warning_msg.append(f"⚠️ 【{category}】預算會超支！")
            
            # 2. 檢查總預算是否會爆
            if (total_spend + amount) > TOTAL_BUDGET:
                warning_msg.append(f"🔥 【總預算】會爆掉！")

            # 如果有警告，顯示出來
            if warning_msg:
                for msg in warning_msg:
                    st.toast(msg, icon="💸")

            # 開始寫入資料
            status_box = st.empty()
            try:
                status_box.info("🔄 連線中...")
                if client:
                    sheet = client.open("記帳本")
                    target_month = date_input.strftime("%Y-%m")
                    
                    try:
                        ws = sheet.worksheet(target_month)
                    except:
                        ws = sheet.add_worksheet(title=target_month, rows=100, cols=10)
                        ws.append_row(['日期', '類別', '細項說明', '金額', '支付方式', '備註'])
                    
                    ws.append_row([
                        date_input.strftime("%Y/%m/%d"),
                        category,
                        item,
                        amount,
                        payment,
                        note
                    ])
                    status_box.success(f"✅ 記帳成功！ (${amount})")
                    time.sleep(1)
                    st.rerun() # 自動刷新
                
            except Exception as e:
                st.error(f"❌ 錯誤: {e}")


