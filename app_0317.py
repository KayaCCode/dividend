import streamlit as st
import pandas as pd
import baostock as bs
import akshare as ak
import os
from datetime import datetime

# ====================== 1. 基础配置与本地存储 ======================
PORTFOLIO_FILE = "portfolio.csv"

def load_portfolio():
    if os.path.exists(PORTFOLIO_FILE):
        return pd.read_csv(PORTFOLIO_FILE, dtype={'代码': str})
    else:
        df = pd.DataFrame([
            {"代码": "600036", "股票名称": "招商银行", "当前持股": 1000, "目标持股": 2000, "当前成本": 32.50, "预期买入价": 30.00},
            {"代码": "600886", "股票名称": "国投电力", "当前持股": 2000, "目标持股": 5000, "当前成本": 13.50, "预期买入价": 14.20}
        ])
        df.to_csv(PORTFOLIO_FILE, index=False, encoding='utf-8-sig')
        return df

def save_portfolio(df):
    df.to_csv(PORTFOLIO_FILE, index=False, encoding='utf-8-sig')

@st.cache_data
def get_stock_name_map():
    try:
        import os
        os.environ['http_proxy'] = ''; os.environ['https_proxy'] = ''
        df = ak.stock_info_a_code_name()
        return dict(zip(df['code'], df['name']))
    except: return {}

def get_stock_display_name(symbol):
    return get_stock_name_map().get(symbol, "未知股票")

# ====================== 2. 数据抓取逻辑 ======================

def get_realtime_price(symbol):
    bs_code = f"sh.{symbol}" if symbol.startswith('6') else f"sz.{symbol}"
    bs.login()
    rs = bs.query_history_k_data_plus(bs_code, "date,close", 
                                      start_date="2025-01-01", frequency="d", adjustflag="2")
    data = []
    while (rs.error_code == '0') & rs.next(): data.append(rs.get_row_data())
    bs.logout()
    try:
        return float(data[-1][1]) if data else 0.0
    except: return 0.0

def get_latest_full_year_dividend(symbol):
    """获取最近一个完整会计年度的总分红（处理多次分红聚合）"""
    try:
        df = ak.stock_dividend_cninfo(symbol=symbol)
        if df.empty: return 0.0
        pay_col = next((c for c in df.columns if '派息' in c and '比例' in c), None)
        report_col = next((c for c in df.columns if '报告时间' in c), None)
        type_col = next((c for c in df.columns if '类型' in c), None)
        
        df['div_per_share'] = pd.to_numeric(df[pay_col], errors='coerce').fillna(0) / 10.0
        df['report_year'] = df[report_col].str.extract(r'(\d{4})').astype(float)
        
        # 按年份聚合总额
        annual_total = df.groupby('report_year')['div_per_share'].sum().reset_index().sort_values('report_year', ascending=False)
        
        # 寻找最近一个含“年报/年度分红”的完整年份
        for _, row in annual_total.iterrows():
            year = row['report_year']
            if not df[(df['report_year'] == year) & (df[type_col].str.contains('年度|年报', na=False))].empty:
                return row['div_per_share']
        return annual_total.iloc[0]['div_per_share'] if not annual_total.empty else 0.0
    except: return 0.0

# ====================== 3. UI 界面 ======================

st.set_page_config(page_title="红利复利管家 v5.0", layout="wide")
st.markdown("<style>.stDataFrame td, .stDataFrame th { text-align: center !important; } [data-testid='stMetricValue'] { text-align: center; }</style>", unsafe_allow_html=True)

tab1, tab2 = st.tabs(["📊 行情聚合看板", "💼 我的持仓管理"])

with tab1:
    st.title("股票行情历史穿透")
    st.info("💡 用于辅助判断个股的历史估值区间。")

with tab2:
    st.title("💼 个人红利账户管理")
    
    if 'portfolio_df' not in st.session_state:
        st.session_state.portfolio_df = load_portfolio()

    edited_df = st.data_editor(
        st.session_state.portfolio_df,
        num_rows="dynamic", use_container_width=True, hide_index=True,
        key="editor_v5_final",
        column_config={
            "代码": st.column_config.TextColumn("代码", required=True),
            "当前持股": st.column_config.NumberColumn("当前持股", min_value=0),
            "目标持股": st.column_config.NumberColumn("目标持股", min_value=0),
            "当前成本": st.column_config.NumberColumn("当前成本", format="%.3f"),
            "预期买入价": st.column_config.NumberColumn("预期买入价", format="%.2f"),
        }
    )

    if not st.session_state.portfolio_df.equals(edited_df):
        st.session_state.portfolio_df = edited_df
        save_portfolio(edited_df)
        st.rerun()

    st.divider()

    if st.button("🚀 执行全仓资产穿透计算", type="primary", key="btn_calc_v5"):
        if edited_df.empty:
            st.warning("请添加持仓数据。")
        else:
            with st.spinner("正在聚合全仓维度数据..."):
                final_rows = []
                # 汇总变量初始化
                stats = {
                    "curr_cost": 0.0,      # 全仓总成本
                    "curr_market": 0.0,    # 当前总市值
                    "target_inv": 0.0,     # 预期目标总投入
                    "curr_div_amt": 0.0,   # 滚动年度总股息
                    "target_div_amt": 0.0  # 目标满仓后年息
                }

                for _, row in edited_df.iterrows():
                    raw_code = str(row.get("代码", "")).strip()
                    if not raw_code: continue
                    code = raw_code.zfill(6) if raw_code.isdigit() else raw_code
                    
                    price = get_realtime_price(code)
                    div_ps = get_latest_full_year_dividend(code) 
                    
                    cur_h = float(row.get("当前持股", 0) or 0)
                    tgt_h = float(row.get("目标持股", 0) or 0)
                    cost_p = float(row.get("当前成本", 0) or 0)
                    exp_p = float(row.get("预期买入价", 0) or 0)

                    # 基础聚合
                    stats["curr_cost"] += (cost_p * cur_h)
                    stats["target_inv"] += (exp_p * tgt_h)
                    stats["curr_div_amt"] += (div_ps * cur_h)
                    stats["target_div_amt"] += (div_ps * tgt_h)

                    if price > 0:
                        stats["curr_market"] += (price * cur_h)
                        profit = (price - cost_p) * cur_h
                        yield_rate = (div_ps / price * 100)
                        display_price = price
                    else:
                        profit, yield_rate, display_price = 0, 0, "数据异常"

                    final_rows.append({
                        "名称": get_stock_display_name(code),
                        "代码": code,
                        "持股进度": (cur_h / tgt_h * 100) if tgt_h > 0 else 100.0,
                        "年度单股红利": div_ps,
                        "当前股价": display_price,
                        "当前盈利": profit,
                        "个股股息率(%)": yield_rate,
                        "本年预期股息": div_ps * cur_h,
                        "满仓预期年息": div_ps * tgt_h
                    })

                if final_rows:
                    res_df = pd.DataFrame(final_rows)
                    st.subheader("📋 持仓穿透明细")
                    st.dataframe(
                        res_df.style.format({
                            "持股进度": "{:.1f}%", "当前盈利": "¥{:,.2f}", "个股股息率(%)": "{:.2f}%",
                            "本年预期股息": "¥{:,.2f}", "满仓预期年息": "¥{:,.2f}", "年度单股红利": "¥{:.3f}"
                        }).bar(subset=['持股进度'], color='#00a65a')
                          .applymap(lambda x: 'color: #ff4b4b' if (isinstance(x, (int, float)) and x > 0) else 'color: #00a65a', subset=['当前盈利']),
                        hide_index=True, width="stretch"
                    )

                    st.divider()
                    
                    # ====================== 资产汇总与目标预判 ======================
                    st.subheader("💰 资产汇总与目标预判")
                    
                    # 块 A：当前持仓现状
                    with st.container(border=True):
                        st.markdown("**🔹 1. 当前持仓现状**")
                        a1, a2, a3, a4 = st.columns(4)
                        a1.metric("全仓总成本", f"¥{stats['curr_cost']:,.2f}")
                        a2.metric("当前总市值", f"¥{stats['curr_market']:,.2f}", 
                                  delta=f"总浮盈 ¥{stats['curr_market'] - stats['curr_cost']:,.2f}")
                        a3.metric("滚动年度总股息", f"¥{stats['curr_div_amt']:,.2f}")
                        curr_acc_yield = (stats['curr_div_amt'] / stats['curr_market'] * 100) if stats['curr_market'] > 0 else 0
                        a4.metric("账户目前股息率", f"{curr_acc_yield:.2f}%")

                    st.write("") # 间距

                    # 块 B：目标持仓预判
                    with st.container(border=True):
                        st.markdown("**🎯 2. 目标持仓预判**")
                        b1, b2, b3 = st.columns(3)
                        b1.metric("预期目标总投入", f"¥{stats['target_inv']:,.2f}")
                        b2.metric("目标满仓后年息", f"¥{stats['target_div_amt']:,.2f}")
                        target_acc_yield = (stats['target_div_amt'] / stats['target_inv'] * 100) if stats['target_inv'] > 0 else 0
                        b3.metric("账户预期满仓股息率", f"{target_acc_yield:.2f}%")