import pandas as pd
import requests
import time
import warnings
import json
import os
from akshare.stock.cons import xq_a_token
import akshare as ak

warnings.filterwarnings("ignore")

# ====================== 自选股持久化配置 ======================
SELF_SELECTED_FILE = "self_selected_stocks.json"
DEFAULT_STOCKS = [
    {"code": "600000", "name": "浦发银行"},
    {"code": "000001", "name": "平安银行"},
    {"code": "601318", "name": "中国平安"}
]

def load_self_selected_stocks():
    """加载自选股数据（修复原生字符串replace参数）"""
    try:
        if os.path.exists(SELF_SELECTED_FILE):
            with open(SELF_SELECTED_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list) and len(data) > 0:
                # 强制补全6位代码 + 清洗名称空格（修复：去掉regex=False）
                for item in data:
                    item["code"] = str(item["code"]).strip().zfill(6)
                    if "name" in item:
                        item["name"] = item["name"].replace(' ', '')  # 核心修复
                # 按代码去重
                df_temp = pd.DataFrame(data)
                df_temp = df_temp.drop_duplicates(subset=['code'], keep='first')
                data = df_temp.to_dict('records')
                
                print(f"✅ 成功加载本地自选股，去重后共 {len(data)} 支标的")
                return data
            else:
                print("⚠️ 本地自选股文件格式异常，使用默认标的")
                return DEFAULT_STOCKS
        else:
            save_self_selected_stocks(DEFAULT_STOCKS)
            print("📄 本地自选股文件不存在，已初始化默认标的")
            return DEFAULT_STOCKS
    except Exception as e:
        print(f"❌ 加载自选股失败：{e}，使用默认标的")
        return DEFAULT_STOCKS

def save_self_selected_stocks(stocks):
    """保存自选股（修复原生字符串replace参数）"""
    try:
        # 统一补全6位代码 + 清洗名称空格（修复：去掉regex=False）
        for item in stocks:
            item["code"] = str(item["code"]).strip().zfill(6)
            if "name" in item:
                item["name"] = item["name"].replace(' ', '')  # 核心修复
        # 去重后保存
        df_temp = pd.DataFrame(stocks)
        df_temp = df_temp.drop_duplicates(subset=['code'], keep='first')
        stocks = df_temp.to_dict('records')
        
        with open(SELF_SELECTED_FILE, "w", encoding="utf-8") as f:
            json.dump(stocks, f, ensure_ascii=False, indent=2)
        print(f"✅ 自选股已保存到本地，去重后共 {len(stocks)} 支标的")
        return True
    except Exception as e:
        print(f"❌ 保存自选股失败：{e}")
        return False

def add_self_selected_stock(code, name):
    """新增自选股（修复原生字符串replace参数）"""
    code = str(code).strip().zfill(6)
    name = name.replace(' ', '')  # 核心修复：去掉regex=False
    stocks = load_self_selected_stocks()
    for stock in stocks:
        if stock["code"] == code:
            print(f"⚠️ 标的 {code}({name}) 已在自选股中，无需重复添加")
            return stocks
    new_stock = {"code": code, "name": name}
    stocks.append(new_stock)
    save_self_selected_stocks(stocks)
    print(f"✅ 新增自选股：{code}({name})")
    return stocks

# ====================== 其余代码完全不变 ======================
def get_xq_token():
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }
    try:
        r = requests.get("https://xueqiu.com/", headers=headers, timeout=10)
        return r.cookies.get("xq_a_token")
    except:
        return None

def fetch_and_save_data():
    print("🚀 启动数据源同步程序...")
    
    token = get_xq_token() or xq_a_token
    headers = {
        "Cookie": f"xq_a_token={token};",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }

    # 加载自选股
    self_selected_stocks = load_self_selected_stocks()
    stock_list = pd.DataFrame(self_selected_stocks)
    # 强制补全6位代码 + 清洗名称空格（pandas的str.replace支持regex=False，保留）
    stock_list['code'] = stock_list['code'].astype(str).str.zfill(6)
    stock_list['name'] = stock_list['name'].str.replace(' ', '', regex=False)
    stock_list = stock_list.to_dict('records') 
    
    csv_file = "data/dividend_data.csv"
    csv_headers = ["代码", "名称", "最新价", "总市值(亿)", "股息率(%)"]
    
    # 初始化CSV文件
    if not os.path.exists(csv_file):
        pd.DataFrame(columns=csv_headers).to_csv(
            csv_file, index=False, encoding='utf-8-sig'
        )
        print(f"📄 初始化CSV文件，已写入表头：{csv_headers}")
    else:
        try:
            df_check = pd.read_csv(csv_file, nrows=1)
            if list(df_check.columns) != csv_headers:
                df_old = pd.read_csv(csv_file, header=None)
                df_old.columns = csv_headers
                df_old.to_csv(csv_file, index=False, encoding='utf-8-sig')
                print(f"🔧 修复CSV表头，已更新为：{csv_headers}")
        except:
            pd.DataFrame(columns=csv_headers).to_csv(
                csv_file, index=False, encoding='utf-8-sig'
            )
            print(f"🔧 CSV文件异常，重新初始化并写入表头：{csv_headers}")
    
    # 清空旧数据
    pd.DataFrame(columns=csv_headers).to_csv(
        csv_file, index=False, encoding='utf-8-sig'
    )
    
    success_count = 0
    valid_codes = 0
    print(f"📥 正在抓取 {len(stock_list)} 支自选股的股息率指标...")

    for i, stock in enumerate(stock_list):
        code = stock['code'].strip()
        # 精准判断雪球代码前缀
        if code.startswith(('60', '68')):
            symbol = f"SH{code}"
        elif code.startswith(('00', '30')):
            symbol = f"SZ{code}"
        elif code.startswith('8'):
            symbol = f"BJ{code}"
        else:
            print(f"⚠️ 跳过非A股代码：{code}")
            continue
        
        valid_codes += 1
        url = f"https://stock.xueqiu.com/v5/stock/quote.json?symbol={symbol}&extend=detail"
        
        try:
            r = requests.get(url, headers=headers, timeout=5)
            if r.status_code != 200:
                print(f"❌ 股票 {code} 响应异常：状态码 {r.status_code}")
                continue
            data = r.json()
            if 'data' not in data or 'quote' not in data['data']:
                print(f"❌ 股票 {code} 数据格式异常")
                continue
            
            quote_data = data['data']['quote']
            dividend_yield = quote_data.get('dividend_yield', None)
            current_price = quote_data.get('current', None)
            market_cap = quote_data.get('market_capital', None)
            
            # 放宽条件：即使股息率为0也保存
            if current_price is not None and market_cap is not None:
                single_data = pd.DataFrame({
                    "代码": [code],
                    "名称": [stock['name']],
                    "最新价": [current_price],
                    "总市值(亿)": [round(market_cap / 1e8, 2)],
                    "股息率(%)": [dividend_yield if dividend_yield is not None else 0]
                })
                single_data.to_csv(
                    csv_file, 
                    mode='a', 
                    index=False, 
                    header=False,
                    encoding='utf-8-sig'
                )
                success_count += 1
            
            time.sleep(0.2)
            
            if i % 10 == 0 and i > 0:
                print(f"✅ 已处理 {i} 支股票，有效A股 {valid_codes} 支，成功抓取 {success_count} 支数据...")
                
        except Exception as e:
            print(f"❌ 处理股票 {code} 失败：{str(e)[:50]}")
            continue

    # 最终排序+去重
    if os.path.exists(csv_file) and success_count > 0:
        df_final = pd.read_csv(csv_file)
        # 1. 清洗名称：去除所有空格（pandas的str.replace保留regex=False）
        df_final['名称'] = df_final['名称'].str.replace(' ', '', regex=False)
        # 2. 强制补全6位代码
        df_final['代码'] = df_final['代码'].astype(str).str.zfill(6)
        # 3. 按代码去重
        df_final = df_final.sort_values(by='股息率(%)', ascending=False)
        df_final = df_final.drop_duplicates(subset=['代码'], keep='first')
        # 4. 重新保存
        df_final.to_csv(csv_file, index=False, encoding='utf-8-sig')
        print(f"\n✨ 任务完成！")
        print(f"📊 统计：有效A股 {valid_codes} 支，去重后实际保存 {len(df_final)} 支数据。")
        print(f"📁 数据已存入 {csv_file}，可在Streamlit看板中查看")
    else:
        print("⚠️ 未抓取到有效数据，请检查Token/网络/自选股代码")

if __name__ == "__main__":
    # add_self_selected_stock("000858", "五粮液")
    # add_self_selected_stock("600519", "贵州茅台")
    fetch_and_save_data()