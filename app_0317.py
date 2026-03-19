import streamlit as st
import pandas as pd
import baostock as bs
import akshare as ak
import re
from datetime import datetime

# ====================== 1. 基础工具与缓存 ======================

@st.cache_data
def get_stock_name_map():
    """获取全量A股代码与名称映射"""
    try:
        import os
        os.environ['http_proxy'] = ''; os.environ['https_proxy'] = ''
        df = ak.stock_info_a_code_name()
        return dict(zip(df['code'], df['name']))
    except:
        return {}

def get_stock_display_name(symbol):
    name_map = get_stock_name_map()
    return name_map.get(symbol, "未知股票")

# ====================== 2. 核心数据抓取逻辑 ======================

def get_ytd_extremes(symbol):
    """获取今年至今(YTD)的价格行情"""
    current_year = datetime.now().year
    start_date = f"{current_year}-01-01"
    end_date = datetime.now().strftime('%Y-%m-%d')
    bs_code = f"sh.{symbol}" if symbol.startswith('6') else f"sz.{symbol}"
    
    bs.login()
    rs = bs.query_history_k_data_plus(bs_code, "date,high,low,close",
                                      start_date=start_date, end_date=end_date,
                                      frequency="d", adjustflag="2")
    data = []
    while (rs.error_code == '0') & rs.next(): data.append(rs.get_row_data())
    bs.logout()
    
    if not data: return None
    df = pd.DataFrame(data, columns=rs.fields)
    for col in ['high', 'low', 'close']: 
        df[col] = pd.to_numeric(df[col], errors='coerce')
    
    return {
        "max": df['high'].max(), 
        "min": df['low'].min(), 
        "last": df['close'].iloc[-1], 
        "year": current_year
    }

def get_baostock_annual_data(symbol, start_year, end_year):
    """获取历年价格极值"""
    name = get_stock_display_name(symbol)
    bs_code = f"sh.{symbol}" if symbol.startswith('6') else f"sz.{symbol}"
    bs.login()
    rs = bs.query_history_k_data_plus(bs_code, "date,high,low,close",
                                      start_date=f"{start_year}-01-01", end_date=f"{end_year}-12-31",
                                      frequency="d", adjustflag="2")
    data = []
    while (rs.error_code == '0') & rs.next(): data.append(rs.get_row_data())
    bs.logout()
    
    if not data: return None, "未找到价格数据"
    
    df = pd.DataFrame(data, columns=rs.fields)
    df['date'] = pd.to_datetime(df['date'])
    for col in ['high', 'low', 'close']: 
        df[col] = pd.to_numeric(df[col], errors='coerce')
    
    annual = df.groupby(df['date'].dt.year).agg({'high': 'max', 'low': 'min', 'close': 'last'}).reset_index()
    annual.columns = ['年份', '年度最高', '年度最低', '年终收盘']
    annual.insert(1, '股票名称', name)
    return annual.sort_values(by='年份', ascending=False), None

def get_dividend_pivot_final(symbol):
    """最终稳定版：基于 CSV 结构优化的数值对齐逻辑"""
    name = get_stock_display_name(symbol)
    try:
        import os
        os.environ['http_proxy'] = ''; os.environ['https_proxy'] = ''
        df = ak.stock_dividend_cninfo(symbol=symbol)
        if df.empty: return None, "接口未返回数据"

        # 1. 直接读取派息比例数值
        pay_col = next((c for c in df.columns if '派息' in c and '比例' in c), None)
        df['10派现'] = pd.to_numeric(df[pay_col], errors='coerce').fillna(0.0) if pay_col else 0.0

        # 2. 智能提取年份 (从“1995年报”等字符串提取)
        report_col = next((c for c in df.columns if '报告时间' in c), None)
        if not report_col: return None, "未找到报告期字段"
        
        df['年份'] = df[report_col].str.extract(r'(\d{4})').astype(float)
        df = df.dropna(subset=['年份'])
        df['年份'] = df['年份'].astype(int)

        # 3. 判定分红类型
        type_col = next((c for c in df.columns if '类型' in c), None)
        def get_label(row):
            t_str = str(row[type_col]) if type_col else ""
            return '10股分红（年报）' if ("年度" in t_str or "年报" in t_str) else '10股分红（中报）'
        
        df['类型'] = [get_label(r) for _, r in df.iterrows()]

        # 4. 透视聚合
        pivot = df.pivot_table(index='年份', columns='类型', values='10派现', aggfunc='sum').fillna(0.0)
        
        for c in ['10股分红（中报）', '10股分红（年报）']:
            if c not in pivot.columns: pivot[c] = 0.0
            
        pivot['10股分红（总）'] = pivot['10股分红（中报）'] + pivot['10股分红（年报）']
        pivot = pivot.reset_index()
        pivot['股票名称'] = name
        
        final_df = pivot[['年份', '股票名称', '10股分红（中报）', '10股分红（年报）', '10股分红（总）']]
        return final_df.sort_values(by='年份', ascending=False), None

    except Exception as e:
        return None, f"解析异常: {str(e)}"

# ====================== 3. Streamlit UI 渲染 ======================

st.set_page_config(page_title="Stock Analysis Dashboard", layout="wide")

# 全局样式：强制表格居中
st.markdown("""
    <style>
    .stDataFrame td, .stDataFrame th { text-align: center !important; }
    [data-testid="stMetricValue"] { text-align: center; }
    </style>
    """, unsafe_allow_html=True)

st.title("📊 股票年度波动与分红看板")

# 输入区
with st.container(border=True):
    c1, c2, c3, c4 = st.columns([2, 1, 1, 2])
    with c1: target_code = st.text_input("股票代码", value="600886")
    with c2: start_y = st.number_input("起始年", 2000, 2026, 2015)
    with c3: end_y = st.number_input("结束年", 2000, 2026, 2025)
    with c4:
        st.write("") 
        run_query = st.button("🚀 点击同步聚合数据", width='stretch', type="primary")

if run_query:
    with st.spinner("数据穿透中..."):
        div_df, div_err = get_dividend_pivot_final(target_code)
        st.session_state['results'] = {
            'stock_name': get_stock_display_name(target_code),
            'ytd': get_ytd_extremes(target_code),
            'hist': get_baostock_annual_data(target_code, start_y, end_y),
            'div': div_df,
            'div_err': div_err
        }

if 'results' in st.session_state:
    res = st.session_state['results']
    
    # 模块 A: 年内即时波动
    if res['ytd']:
        y = res['ytd']
        st.subheader(f"✨ {res['stock_name']} ({target_code}) - {y['year']} 年内行情")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("年内最高", f"¥{y['max']:.2f}")
        m2.metric("年内最低", f"¥{y['min']:.2f}")
        m3.metric("当前收盘", f"¥{y['last']:.2f}")
        amp = (y['max']-y['min'])/y['min']*100 if y['min'] > 0 else 0
        m4.metric("年内振幅", f"{amp:.2f}%")

    st.divider()
    
    # 模块 B & C: 双表并列展示
    col_l, col_r = st.columns([4.5, 5.5])
    
    with col_l:
        st.subheader("🗓️ 历年价格极值")
        p_df, p_err = res['hist']
        if p_err: st.warning(p_err)
        else:
            st.dataframe(p_df.style.format(subset=['年度最高', '年度最低', '年终收盘'], precision=2), 
                         hide_index=True, width='stretch')

    with col_r:
        st.subheader("💰 历年分红聚合")
        if res['div_err']: st.error(res['div_err'])
        elif res['div'] is not None:
            st.dataframe(res['div'].style.format(subset=['10股分红（中报）', '10股分红（年报）', '10股分红（总）'], precision=3), 
                         hide_index=True, width='stretch')
            st.caption("✅ 数据说明：分红金额已按所属财务报告年度自动归集。")
else:
    st.info("💡 请在上方输入股票代码并点击查询按钮。")