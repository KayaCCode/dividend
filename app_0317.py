import streamlit as st
import pandas as pd
import baostock as bs
import akshare as ak
import re
from datetime import datetime

# ====================== 核心逻辑函数 ======================

def get_ytd_extremes(symbol):
    """获取今年至今(YTD)的价格极值"""
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
    df = pd.DataFrame(data, columns=rs.fields).apply(pd.to_numeric, errors='ignore')
    return {
        "max": df['high'].max(), 
        "min": df['low'].min(), 
        "last": df['close'].iloc[-1], 
        "count": len(df),
        "year": current_year
    }

def get_baostock_annual_data(symbol, start_year, end_year):
    """获取历史年度价格极值"""
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
    for col in ['high', 'low', 'close']: df[col] = pd.to_numeric(df[col])
    
    annual = df.groupby(df['date'].dt.year).agg({
        'high': 'max', 'low': 'min', 'close': 'last'
    }).reset_index()
    annual.columns = ['年份', '年度最高', '年度最低', '年终收盘']
    return annual.sort_values(by='年份', ascending=False), None

def get_dividend_pivot(symbol):
    """获取分红并整理为：一年一行，区分中报/年报/总计"""
    import os
    os.environ['http_proxy'] = ''; os.environ['https_proxy'] = ''
    try:
        df = ak.stock_dividend_cninfo(symbol=symbol)
        if df.empty: return None, "暂无分红数据"
        
        if '实施方案公告日期' in df.columns:
            df = df.rename(columns={'实施方案公告日期': '公告日期', '实施方案分红说明': '分红方案说明'})
        df['公告日期'] = pd.to_datetime(df['公告日期'])
        
        def extract_10_pay(desc):
            m = re.search(r'10派([\d\.]+)元', str(desc))
            return float(m.group(1)) if m else 0.0
        df['10派现'] = df['分红方案说明'].apply(extract_10_pay)
        
        def calibrate_info(row):
            dt = row['公告日期']
            if 4 <= dt.month <= 7:
                return dt.year - 1, '10股分红（年报）'
            elif 8 <= dt.month <= 11:
                return dt.year, '10股分红（中报）'
            return dt.year, '其他'

        df[['所属年份', '分红类型']] = df.apply(calibrate_info, axis=1, result_type='expand')
        
        pivot = df.pivot_table(index='所属年份', columns='分红类型', values='10派现', aggfunc='sum').fillna(0)
        
        for col in ['10股分红（中报）', '10股分红（年报）']:
            if col not in pivot.columns: pivot[col] = 0.0
            
        pivot['10股分红（总）'] = pivot['10股分红（中报）'] + pivot['10股分红（年报）']
        pivot = pivot[['10股分红（中报）', '10股分红（年报）', '10股分红（总）']].reset_index()
        pivot = pivot.rename(columns={'所属年份': '年份'})
        return pivot.sort_values(by='年份', ascending=False), None
    except Exception as e:
        return None, f"分红解析失败: {str(e)}"

# ====================== Streamlit 样式与页面 ======================
st.set_page_config(page_title="Stock Analysis Pro", layout="wide")

# CSS 强制居中样式补丁
st.markdown("""
    <style>
    /* 强制所有表格单元格和表头文字居中 */
    .stDataFrame [data-testid="stTable"] td, 
    .stDataFrame [data-testid="stTable"] th,
    .stDataFrame [data-testid="stTable"] [data-testid="styled-table-cell"] {
        text-align: center !important;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("📊 股票年度波动与分红聚合看板")

with st.container(border=True):
    c1, c2, c3, c4 = st.columns([2, 1, 1, 2])
    with c1: 
        target_code = st.text_input("股票代码", value="600941")
    with c2: 
        # 修改点：min_value 从 2010 改为 2000
        start_y = st.number_input("起始年", min_value=2000, max_value=2026, value=2018)
    with c3: 
        end_y = st.number_input("结束年", min_value=2000, max_value=2026, value=2025)
    with c4:
        st.write("") 
        run_query = st.button("🚀 一键查询聚合数据", use_container_width=True, type="primary")

if run_query:
    with st.spinner("正在聚合多源历史数据..."):
        st.session_state['results'] = {
            'ytd': get_ytd_extremes(target_code),
            'hist': get_baostock_annual_data(target_code, start_y, end_y),
            'div': get_dividend_pivot(target_code)
        }

if 'results' in st.session_state:
    res = st.session_state['results']
    
    # 模块 1: YTD Metrics
    if res['ytd']:
        y = res['ytd']
        st.subheader(f"✨ {y['year']} 年内即时波动")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("年内最高", f"¥{y['max']:.2f}")
        m2.metric("年内最低", f"¥{y['min']:.2f}")
        m3.metric("当前价格", f"¥{y['last']:.2f}")
        amp = (y['max'] - y['min']) / y['min'] * 100
        m4.metric("年内振幅", f"{amp:.2f}%")
    
    st.divider()
    
    # 模块 2 & 3: 分栏显示
    col_l, col_r = st.columns([4, 6])
    
    # 统一样式函数：居中 + 格式化
    def style_center(df, precision=2):
        return df.style.set_properties(**{
            'text-align': 'center'
        }).format(precision=precision)

    with col_l:
        st.subheader("🗓️ 历年价格极值")
        df_p, err_p = res['hist']
        if err_p: st.warning(err_p)
        else:
            # 价格表格应用居中样式
            st.dataframe(style_center(df_p, 2), hide_index=True, use_container_width=True)

    with col_r:
        st.subheader("💰 历年分红聚合 (10股派现)")
        df_d, err_d = res['div']
        if err_d: st.error(err_d)
        else:
            # 分红表格应用居中样式，保留三位小数
            st.dataframe(style_center(df_d, 3), hide_index=True, use_container_width=True)
            st.caption("注：数据基于公告月份自动归集。5-7月公告归为上年年报，8-11月归为当年中报。")
else:
    st.info("💡 请输入代码并点击查询。")