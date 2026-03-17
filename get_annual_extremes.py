import requests
import pandas as pd
import time
import re
from datetime import datetime, timedelta

# ==================== 配置部分 ====================
# 请前往 iTick 官网 (https://www.itick.org) 注册获取免费 API Token
ITICK_TOKEN = ""  # 替换为你的实际 Token
ITICK_HEADERS = {
    "accept": "application/json",
    "token": ITICK_TOKEN
}
ITICK_BASE_URL = "https://api.itick.org"

# ==================== 核心功能：使用 iTick API 获取价格数据 ====================

def get_itick_kline(symbol, start_year, end_year):
    """
    使用 iTick API 获取股票历史K线数据（最可靠的免费源）
    
    参数:
        symbol: 股票代码，如 "600941.SH" (格式: 代码.市场, SH=上交所, SZ=深交所)
        start_year: 开始年份
        end_year: 结束年份
    
    返回:
        DataFrame 或 None
    """
    # 解析市场代码
    if '.' in symbol:
        code, market = symbol.split('.')
    else:
        # 默认处理：6开头是沪市，0/3开头是深市
        if symbol.startswith('6'):
            market = 'SH'
        else:
            market = 'SZ'
        code = symbol
    
    # 构建日期范围
    start_date = f"{start_year}-01-01"
    end_date = f"{end_year}-12-31"
    
    # iTick K线接口 - 日线数据 (kType=8 表示日K线)[citation:2][citation:5]
    url = f"{ITICK_BASE_URL}/stock/kline"
    params = {
        "region": "CN",           # 中国市场
        "code": f"{market}${code}",  # 格式如 "SH$600941"
        "kType": "8",             # 日K线
        "start_date": start_date,
        "end_date": end_date,
        "limit": "2000"           # 获取足够多的条数
    }
    
    try:
        print(f"正在从 iTick 获取 {symbol} 的历史数据...")
        response = requests.get(url, headers=ITICK_HEADERS, params=params, timeout=10)
        data = response.json()
        
        if data.get("code") == 0:
            kline_data = data.get("data", [])
            if not kline_data:
                print("未获取到数据")
                return None
            
            # 转换为 DataFrame
            df = pd.DataFrame(kline_data)
            
            # 转换时间戳并设置索引
            df['datetime'] = pd.to_datetime(df['t'], unit='ms')
            df.set_index('datetime', inplace=True)
            
            # 重命名列并选择需要的字段
            df = df[['o', 'h', 'l', 'c', 'v']]  # o=开盘, h=最高, l=最低, c=收盘, v=成交量
            df.columns = ['开盘', '最高', '最低', '收盘', '成交量']
            
            # 转换为数值类型
            for col in ['开盘', '最高', '最低', '收盘', '成交量']:
                df[col] = pd.to_numeric(df[col])
            
            print(f"成功获取 {len(df)} 条日K线数据")
            return df
        else:
            print(f"API 返回错误: {data.get('msg')}")
            return None
            
    except Exception as e:
        print(f"iTick 请求失败: {e}")
        return None

def get_annual_extremes(symbol, start_year, end_year):
    """
    获取年度最高/最低价（优先使用 iTick，失败时尝试 AKShare 备用）
    """
    # 优先使用 iTick
    df = get_itick_kline(symbol, start_year, end_year)
    
    # 如果 iTick 失败，尝试 AKShare 的腾讯源作为备用
    if df is None or df.empty:
        print("iTick 获取失败，尝试备用数据源...")
        return get_annual_extremes_akshare(symbol, start_year, end_year)
    
    # 聚合年度数据
    df['年份'] = df.index.year
    annual_data = df.groupby('年份').agg({
        '最高': 'max',
        '最低': 'min',
        '收盘': 'last'
    })
    
    return annual_data

# ==================== 备用方案：AKShare 腾讯源 ====================

def get_annual_extremes_akshare(symbol, start_year, end_year):
    """
    AKShare 备用方案 - 使用腾讯源（比东方财富源更稳定）
    """
    try:
        import akshare as ak
        
        # 使用腾讯源获取数据
        stock_df = ak.stock_zh_a_hist_tx(
            symbol=symbol,
            start_date=f"{start_year}0101",
            end_date=f"{end_year}1231",
            adjust="qfq"
        )
        
        if stock_df.empty:
            return pd.DataFrame()
        
        stock_df['日期'] = pd.to_datetime(stock_df['日期'])
        stock_df.set_index('日期', inplace=True)
        
        annual_data = stock_df.resample('YE').agg({
            '最高': 'max',
            '最低': 'min',
            '收盘': 'last'
        })
        annual_data.index = annual_data.index.year
        annual_data.index.name = '年份'
        return annual_data
        
    except Exception as e:
        print(f"备用数据源也失败: {e}")
        return pd.DataFrame()

# ==================== 分红数据（使用 AKShare，已验证稳定） ====================

def get_dividend_history(symbol):
    """
    获取分红数据（使用 AKShare 巨潮资讯源，已验证稳定）
    """
    try:
        import akshare as ak
        
        dividend_df = ak.stock_dividend_cninfo(symbol=symbol)
        
        if dividend_df.empty:
            print(f"警告：未获取到 {symbol} 的分红数据")
            return pd.DataFrame()

        # 适配新版列名
        if '实施方案公告日期' in dividend_df.columns:
            dividend_df = dividend_df.rename(columns={
                '实施方案公告日期': '公告日期',
                '实施方案分红说明': '分红方案说明'
            })

        # 检查必要列
        if '公告日期' not in dividend_df.columns or '分红方案说明' not in dividend_df.columns:
            print(f"警告：缺少必要列，实际列名：{list(dividend_df.columns)}")
            return pd.DataFrame()

        dividend_df['公告日期'] = pd.to_datetime(dividend_df['公告日期'])

        def extract_dividend_per_share(desc):
            """从 '10派X元' 提取每股股利"""
            desc = str(desc)
            match = re.search(r'10派([\d\.]+)元', desc)
            if match:
                return float(match.group(1)) / 10.0
            match = re.search(r'派([\d\.]+)元', desc)
            if match:
                return float(match.group(1))
            return 0.0

        dividend_df['每股股利'] = dividend_df['分红方案说明'].apply(extract_dividend_per_share)

        return dividend_df.sort_values(by='公告日期', ascending=False)
        
    except Exception as e:
        print(f"获取分红数据失败: {e}")
        return pd.DataFrame()

# ==================== 主程序 ====================

if __name__ == "__main__":
    # 股票代码 - iTick 格式要求：代码.市场 (SH=上交所, SZ=深交所)
    stock_code = "600941"  # 中国移动 沪市
    # 备用格式（如果不习惯带市场后缀，也可用纯数字，函数会自动判断）
    # stock_code = "600941"
    
    print("="*50)
    print("股票数据分析工具")
    print("="*50)
    
    # 1. 获取年度价格数据
    print("\n▶ 正在获取价格数据...")
    price_stats = get_annual_extremes(stock_code, 2021, 2025)
    
    if not price_stats.empty:
        print(f"\n>>> 股票 {stock_code} 年度价格统计:")
        print("="*40)
        print(price_stats.round(2))  # 保留两位小数
        print("="*40)
    else:
        print("✗ 无法获取价格数据，请检查网络或股票代码。")
    
    # 2. 获取分红数据
    print("\n▶ 正在获取分红数据...")
    dividends = get_dividend_history(stock_code.split('.')[0])  # 取纯数字部分
    
    if not dividends.empty:
        print(f"\n>>> 股票 {stock_code} 历史分红详情 (前10条):")
        print("="*60)
        cols_to_show = ['公告日期', '分红类型', '分红方案说明', '每股股利', '股权登记日', '除权日']
        existing_cols = [c for c in cols_to_show if c in dividends.columns]
        print(dividends[existing_cols].head(10).to_string(index=False))
        print("="*60)
    else:
        print("✗ 无法获取分红数据，跳过分红显示。")
    
    print("\n✓ 程序执行完成")