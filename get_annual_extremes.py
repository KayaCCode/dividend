import akshare as ak
import pandas as pd
import time
import re

def get_stock_data_with_retry(func, **kwargs):
    """
    通用重试装饰器，应对 Remote end closed connection 错误
    """
    for i in range(3):
        try:
            df = func(**kwargs)
            if df is not None and not df.empty:
                return df
        except Exception as e:
            print(f"请求失败，正在进行第 {i+1} 次重试... 错误原因: {e}")
            time.sleep(2)
    return pd.DataFrame()

def get_annual_extremes(symbol, start_year, end_year):
    """获取年度最高/最低价"""
    params = {
        "symbol": symbol,
        "period": "daily",
        "start_date": f"{start_year}0101",
        "end_date": f"{end_year}1231",
        "adjust": "qfq"
    }
    
    stock_df = get_stock_data_with_retry(ak.stock_zh_a_hist, **params)
    
    if stock_df.empty:
        return "未能获取到价格数据，请检查网络或股票代码。"

    stock_df['日期'] = pd.to_datetime(stock_df['日期'])
    stock_df.set_index('日期', inplace=True)
    
    # 聚合年度数据
    annual_data = stock_df.resample('YE').agg({
        '最高': 'max',
        '最低': 'min',
        '收盘': 'last'
    })
    annual_data.index = annual_data.index.year
    annual_data.index.name = '年份'
    return annual_data

def get_dividend_history(symbol):
    """获取分红数据并解析派现金额"""
    dividend_df = get_stock_data_with_retry(ak.stock_dividend_cninfo, symbol=symbol)
    
    if dividend_df.empty:
        return pd.DataFrame()

    # 简单清洗
    dividend_df['公告日期'] = pd.to_datetime(dividend_df['公告日期'])
    
    # 正则提取“10派X元”中的X
    def parse_cash(x):
        res = re.findall(r'派([\d\.]+)元', str(x))
        return float(res[0]) / 10 if res else 0.0

    dividend_df['每股股利'] = dividend_df['分红方案说明'].apply(parse_cash)
    
    return dividend_df.sort_values(by='公告日期', ascending=False)

# --- 执行脚本 ---
if __name__ == "__main__":
    stock_code = "600941"  # 中国移动 (示例)
    
    # 1. 获取年度价格波动
    price_stats = get_annual_extremes(stock_code, 2021, 2025)
    print(f"\n>>> 股票 {stock_code} 年度价格统计:")
    print(price_stats)

    # 2. 获取分红详情
    dividends = get_dividend_history(stock_code)
    if not dividends.empty:
        print(f"\n>>> 股票 {stock_code} 历史分红详情 (前10条):")
        cols = ['公告日期', '分红方案说明', '每股股利', '除权除息日']
        print(dividends[cols].head(10))