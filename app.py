import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
from datetime import datetime
import pandas as pd
import time

# ==========================================
# 🎯 預算設定區
# ==========================================
BUDGET_CONFIG = {
    "生存": 6000,       # 吃飯、交通
    "享樂": 3000,       # 網購、玩樂
    "投資/儲蓄": 1000   # 存錢
}
BASE_BUDGET = 10000     # 這是您的「底薪」或是「基本預算」
# ==========================================

# --- 設定網頁標題 ---
st.set_page_config(page_title="2026 財務指揮中心", page_icon="💰")

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

st.title("💰 我的記帳 APP (收支整合版)")

# ===========================
# 🛡️ Level 5：動態預算儀表板
# ===========================
client = connect_to_gsheet()

# 初始化變數
current_spends = {k: 0 for k in BUDGET_CONFIG.keys()} # 只歸零支出類別
total_spend = 0
total_income = 0 # 新增：收入變數

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
                
                # --- 🔥 關鍵修改：把資料分成「收入」跟「支出」兩堆 ---
                
                # 1. 算收入 (類別是 '收入' 的加總)
                total_income = df[df['類別'] == '收入']['金額'].sum()
                
                # 2. 算支出 (類別不是 '收入' 的才是支出)
                expense_df = df[df['類別'] != '收入']
                total_spend = expense_df['金額'].sum()

                # 3. 算各個分類的支出 (只從支出堆裡找)
                for category in BUDGET_CONFIG.keys():
                    current_spends[category] = expense_df[expense_df['類別'] == category]['金額'].sum()
                
        except:
            pass # 新月份無資料

        # --- 1. 總資產大看板 ---
        st.subheader(f"📅 本月收支戰況 ({target_month})")
        
        # 動態總預算 = 基本預算 + 賺到的錢
        dynamic_total_budget = BASE_BUDGET + total_income
        total_remain = dynamic_total_budget - total_spend
        
        # 進度條計算 (分母變大了)
        total_progress = min(total_spend / dynamic_total_budget, 1.0) if dynamic_total_budget > 0 else 0
        
        # 顯示四個數據：基本預算 / 額外收入 / 已花費 / 剩餘
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("基本預算", f"${BASE_BUDGET}")
        c2.metric("額外收入", f"${int(total_income)}", delta="加菜金") # 顯示賺了多少
        c3.metric("總花費", f"${int(total_spend)}")
        c4.metric("剩餘可花", f"${int(total_remain)}", 
                  delta=f"{int(total_remain)}", 
                  delta_color="normal" if total_remain > 0 else "inverse")
        
        if total_spend > dynamic_total_budget:
            st.error(f"🔥 警告！總預算已爆表！超支 ${int(total_spend - dynamic_total_budget)}")
        else:
            st.progress(total_progress)
            st.caption(f"目前額度使用率：{int(total_progress*100)}% (包含收入加成)")

        st.markdown("---")

        # --- 2. 各支出分類詳情 ---
        st.caption("📊 各類別支出監控")
        cols = st.columns(3)
        
        for idx, (cat, budget) in enumerate(BUDGET_CONFIG.items()):
            spend = current_spends[cat]
            remain = budget - spend
            
            with cols[idx]:
                st.write(f"**{cat}**")
                st.write(f"限額: ${budget}")
                if spend > budget:
                    st.markdown(f":red[⚠️ 已超支 ${int(spend - budget)}]")
                else:
                    st.progress(min(spend/budget, 1.0) if budget > 0 else 0)
                    st.caption(f"剩 ${int(remain)}")

        st.markdown("---")

    except Exception as e:
        # st.error(e) # 除錯用
        pass

# ===========================
# 📝 記帳輸入區
# ===========================
with st.form("entry_form", clear_on_submit=True):
    col1, col2 = st.columns(2)
    with col1:
        date_input = st.date_input("日期", datetime.now())
    with col2:
        # 🔥 修改：把「收入」加進選單裡，並且放在第一個方便選
        category_options = ["收入"] + list(BUDGET_CONFIG.keys())
        category = st.selectbox("類別", category_options)
    
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
            # 🔥 智慧防爆檢查 (收入不用檢查會不會爆)
            warning_msg = []
            
            if category != "收入":
                # 1. 檢查該類別是否會爆
                if (current_spends[category] + amount) > BUDGET_CONFIG[category]:
                    warning_msg.append(f"⚠️ 【{category}】預算會超支！")
                
                # 2. 檢查總預算是否會爆 (用動態預算來比)
                # 這裡的邏輯是：雖然你有賺錢，但如果花費超過 (底薪+收入)，還是會警告
                dynamic_total_budget = BASE_BUDGET + total_income
                if (total_spend + amount) > dynamic_total_budget:
                    warning_msg.append(f"🔥 【總資產】會透支！賺得不夠花啊！")

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
                    # 判斷是收入還是支出，給不同的成功訊息
                    if category == "收入":
                        status_box.success(f"💰 收入入帳！資金增加 ${amount}")
                        st.balloons() # 收入就是要放氣球慶祝
                    else:
                        status_box.success(f"✅ 記帳成功！ (${amount})")
                    
                    time.sleep(1)
                    st.rerun()
                
            except Exception as e:
                st.error(f"❌ 錯誤: {e}")
