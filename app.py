import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime

# ====================== 自选股持久化核心函数 ======================
SELF_SELECTED_FILE = "self_selected_stocks.json"
DEFAULT_WATCHLIST = ["600036", "601398", "000001", "601939"]

def load_watchlist_from_file():
    """从本地文件加载自选股列表"""
    try:
        if os.path.exists(SELF_SELECTED_FILE):
            with open(SELF_SELECTED_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            # 提取代码列表 + 补全6位 + 去重
            watchlist = [item["code"].zfill(6) for item in data if "code" in item]
            watchlist = list(dict.fromkeys(watchlist))  # 保持顺序去重
            return watchlist if watchlist else DEFAULT_WATCHLIST
        else:
            return DEFAULT_WATCHLIST
    except Exception as e:
        st.warning(f"加载自选股失败，使用默认列表：{e}")
        return DEFAULT_WATCHLIST

def save_watchlist_to_file(watchlist):
    """将自选股列表保存到本地文件"""
    try:
        # 补全6位代码 + 匹配名称
        df = pd.read_csv("data/dividend_data.csv", dtype={'代码': str}) if os.path.exists("data/dividend_data.csv") else pd.DataFrame()
        watchlist_data = []
        for code in watchlist:
            code = code.strip().zfill(6)
            # 匹配名称，无则显示"未知名称"
            name = df[df['代码'] == code]['名称'].values[0] if not df.empty and code in df['代码'].values else "未知名称"
            name = name.replace(' ', '')
            watchlist_data.append({"code": code, "name": name})
        # 去重后保存
        df_temp = pd.DataFrame(watchlist_data)
        df_temp = df_temp.drop_duplicates(subset=['code'], keep='first')
        watchlist_data = df_temp.to_dict('records')
        
        with open(SELF_SELECTED_FILE, "w", encoding="utf-8") as f:
            json.dump(watchlist_data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        st.error(f"保存自选股失败：{e}")
        return False

# ====================== 页面配置与样式 ======================
st.set_page_config(
    page_title="A股红利价值看板",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自定义 CSS 样式
st.markdown("""
    <style>
    .main {
        background-color: #0e1117;
    }
    .stDataFrame {
        border-radius: 10px;
    }
    div[data-testid="metric-container"] {
        background-color: #1e2130;
        border: 1px solid #4a4a4a;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }
    </style>
    """, unsafe_allow_html=True)

# ====================== 数据加载函数 ======================
@st.cache_data
def load_data():
    try:
        # 确保代码列被读取为字符串，防止丢失开头的0
        df = pd.read_csv("data/dividend_data.csv", dtype={'代码': str})
        # 简单清洗数据，确保股息率是数字
        df['股息率(%)'] = pd.to_numeric(df['股息率(%)'], errors='coerce')
        # 补全6位代码 + 清洗名称空格 + 去重
        df['代码'] = df['代码'].str.zfill(6)
        df['名称'] = df['名称'].str.replace(' ', '', regex=False)
        df = df.drop_duplicates(subset=['代码'], keep='first')
        return df
    except FileNotFoundError:
        st.error("未找到数据文件 dividend_data.csv，请先运行数据更新脚本。")
        return pd.DataFrame()

# ====================== 新增：添加序号列的函数 ======================
def add_serial_number(df):
    """给DataFrame添加序号列（从1开始），放在第一列"""
    df_with_serial = df.copy()
    df_with_serial.insert(0, '序号', range(1, len(df_with_serial) + 1))
    return df_with_serial

# ====================== 统一的格式化函数（适配序号列） ======================
def format_dataframe(data):
    # 先添加序号列
    data_with_serial = add_serial_number(data)
    # 格式化显示
    return data_with_serial.style.format({
        '最新价': '{:.2f}',
        '总市值(亿)': '{:,.0f}',
        '股息率(%)': '{:.2f}%'
    }).background_gradient(subset=['股息率(%)'], cmap='YlGn')

# ====================== 主页面内容 ======================
# 侧边栏
with st.sidebar:
    st.image("https://www.freeiconspng.com/uploads/stock-exchange-icon-png-11.png", width=80)
    st.title("红利策略配置")
    st.info("本看板每日收盘后更新，基于静态股息率筛选。")
    
    st.subheader("⭐ 自选股监控")
    # 初始化session_state
    if "watchlist" not in st.session_state:
        st.session_state["watchlist"] = load_watchlist_from_file()
    # 将列表转为字符串，方便显示在文本框中
    watchlist_default = ", ".join(st.session_state["watchlist"])
    # 文本框输入
    watchlist_input = st.text_area(
        "输入股票代码(每行一个或逗号隔开)", 
        watchlist_default,
        key="watchlist_input"
    ).upper()
    # 解析输入的自选股列表 + 补全6位 + 去重
    watchlist = [x.strip().zfill(6) for x in watchlist_input.replace('\n', ',').split(',') if x.strip()]
    watchlist = list(dict.fromkeys(watchlist))  # 保持顺序去重
    # 保存按钮
    if st.button("💾 保存自选股"):
        st.session_state["watchlist"] = watchlist
        save_status = save_watchlist_to_file(watchlist)
        if save_status:
            st.success("自选股已保存！刷新页面不会丢失")
        else:
            st.error("自选股保存失败，请检查日志！")

    st.divider()
    st.markdown("### 筛选参数")
    min_market_cap = st.slider("最低市值 (亿元)", 0, 5000, 1000)

# 获取数据
df = load_data()

if not df.empty:
    # 头部标题区
    col_title, col_time = st.columns([3, 1])
    with col_title:
        st.title("💹 A股红利价值看板")
        st.caption("汇聚 A 股核心资产，聚焦高股息现金牛")
    with col_time:
        st.write("")
        st.metric(label="数据日期", value=datetime.now().strftime("%Y-%m-%d"))

    # 顶部概览指标卡
    st.write("---")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("A股红利标的池总数", len(df), delta="实时同步")
    m2.metric("千亿市值数量", len(df[df['总市值(亿)'] >= 1000]))
    avg_yield = df['股息率(%)'].mean()
    m3.metric("市场平均股息率", f"{avg_yield:.2f}%")
    m4.metric("最高股息率", f"{df['股息率(%)'].max():.2f}%")

    # 主展示区
    st.write("### 📊 核心策略清单")
    tab1, tab2, tab3 = st.tabs(["🔥 全市场高股息 Top 20", "💎 蓝筹高股息 (千亿市值)", "📋 自选股动态"])

    with tab1:
        top_20_all = df.sort_values(by='股息率(%)', ascending=False).head(20)
        st.dataframe(format_dataframe(top_20_all), use_container_width=True, height=750)

    with tab2:
        big_caps = df[df['总市值(亿)'] >= min_market_cap]
        top_20_big = big_caps.sort_values(by='股息率(%)', ascending=False).head(20)
        st.dataframe(format_dataframe(top_20_big), use_container_width=True, height=750)

    with tab3:
        current_watchlist = st.session_state.get("watchlist", [])
        if current_watchlist:
            # 确保代码是6位字符串，匹配数据中的格式
            my_stocks = df[df['代码'].isin(current_watchlist)]
            # 二次兜底去重
            my_stocks = my_stocks.drop_duplicates(subset=['代码'], keep='first')
            if not my_stocks.empty:
                st.dataframe(format_dataframe(my_stocks), use_container_width=True)
            else:
                st.warning("自选股列表中暂无匹配的股息率数据，请检查代码是否正确。")
        else:
            st.info("在左侧输入股票代码并点击「保存自选股」即可开启监控。")

    # 页脚
    st.divider()
    st.markdown("""
        <div style="text-align: center; color: #666;">
            <p>数据来源：AKShare / 开源金融社区</p>
            <p>© 2024 Dividend Dashboard Expert - 投资有风险，入市需谨慎</p>
        </div>
    """, unsafe_allow_html=True)

else:
    st.warning("等待初始化数据中...请先运行数据抓取脚本生成 dividend_data.csv 文件")