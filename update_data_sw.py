import pandas as pd
import requests
import time
import warnings
import os
from io import StringIO
from bs4 import BeautifulSoup
from akshare.utils.cons import headers

warnings.filterwarnings("ignore")

def sw_index_third_info() -> pd.DataFrame:
    """获取所有申万三级行业代码（用于遍历抓取全A股）"""
    url = "https://legulegu.com/stockdata/sw-industry-overview"
    r = requests.get(url, headers=headers)
    soup = BeautifulSoup(r.text, features="lxml")
    code_raw = soup.find(name="div", attrs={"id": "level3Items"}).find_all(
        name="div", attrs={"class": "lg-industries-item-chinese-title"}
    )
    name_raw = soup.find(name="div", attrs={"id": "level3Items"}).find_all(
        name="div", attrs={"class": "lg-industries-item-number"}
    )
    value_raw = soup.find(name="div", attrs={"id": "level3Items"}).find_all(
        name="div", attrs={"class": "lg-sw-industries-item-value"}
    )
    code = [item.get_text() for item in code_raw]
    name = [item.get_text().split("(")[0] for item in name_raw]
    parent_name = [
        item.find("span").get_text().split("(")[0][1:-1] for item in name_raw
    ]
    num = [item.get_text().split("(")[1].split(")")[0] for item in name_raw]
    num_1 = [
        item.find_all("span", attrs={"class": "value"})[0].get_text().strip()
        for item in value_raw
    ]
    num_2 = [
        item.find_all("span", attrs={"class": "value"})[1].get_text().strip()
        for item in value_raw
    ]
    num_3 = [
        item.find_all("span", attrs={"class": "value"})[2].get_text().strip()
        for item in value_raw
    ]
    num_4 = [
        item.find_all("span", attrs={"class": "value"})[3].get_text().strip()
        for item in value_raw
    ]
    temp_df = pd.DataFrame([code, name, parent_name, num, num_1, num_2, num_3, num_4]).T
    temp_df.columns = [
        "行业代码",
        "行业名称",
        "上级行业",
        "成份个数",
        "静态市盈率",
        "TTM(滚动)市盈率",
        "市净率",
        "静态股息率",
    ]
    temp_df["成份个数"] = pd.to_numeric(temp_df["成份个数"], errors="coerce")
    temp_df["静态市盈率"] = pd.to_numeric(temp_df["静态市盈率"], errors="coerce")
    temp_df["TTM(滚动)市盈率"] = pd.to_numeric(temp_df["TTM(滚动)市盈率"], errors="coerce")
    temp_df["市净率"] = pd.to_numeric(temp_df["市净率"], errors="coerce")
    temp_df["静态股息率"] = pd.to_numeric(temp_df["静态股息率"], errors="coerce")
    return temp_df

def sw_index_third_cons(symbol: str = "801120.SI") -> pd.DataFrame:
    """抓取指定申万三级行业下的所有个股数据（含股息率）"""
    try:
        url = f"https://legulegu.com/stockdata/index-composition?industryCode={symbol}"
        r = requests.get(url, headers=headers, timeout=10)
        temp_df = pd.read_html(StringIO(r.text))[0]
        temp_df.columns = [
            "序号",
            "股票代码",
            "股票简称",
            "纳入时间",
            "申万1级",
            "申万2级",
            "申万3级",
            "价格",
            "市盈率",
            "市盈率ttm",
            "市净率",
            "股息率",
            "市值",
            "归母净利润同比增长(09-30)",
            "归母净利润同比增长(06-30)",
            "营业收入同比增长(09-30)",
            "营业收入同比增长(06-30)",
        ]
        # 数据清洗
        temp_df["价格"] = pd.to_numeric(temp_df["价格"], errors="coerce")
        temp_df["市盈率"] = pd.to_numeric(temp_df["市盈率"], errors="coerce")
        temp_df["市盈率ttm"] = pd.to_numeric(temp_df["市盈率ttm"], errors="coerce")
        temp_df["市净率"] = pd.to_numeric(temp_df["市净率"], errors="coerce")
        # 处理股息率（去掉%并转数字）
        temp_df["股息率"] = temp_df["股息率"].astype(str).str.strip("%")
        temp_df["股息率"] = pd.to_numeric(temp_df["股息率"], errors="coerce")
        temp_df["市值"] = pd.to_numeric(temp_df["市值"], errors="coerce")
        
        # 清理同比增长字段
        for col in ["归母净利润同比增长(09-30)", "归母净利润同比增长(06-30)",
                    "营业收入同比增长(09-30)", "营业收入同比增长(06-30)"]:
            temp_df[col] = temp_df[col].astype(str).str.strip("%")
            temp_df[col] = pd.to_numeric(temp_df[col], errors="coerce")
        
        return temp_df
    except Exception as e:
        print(f"❌ 抓取行业 {symbol} 失败：{e}")
        return pd.DataFrame()

def fetch_and_save_dividend_data():
    """主函数：遍历所有申万三级行业，抓取全A股股息率并追加写入CSV"""
    print("🚀 启动乐咕乐股A股股息率抓取程序...")
    csv_file = "dividend_data_shenwan.csv"
    csv_headers = ["代码", "名称", "最新价", "总市值(亿)", "股息率(%)", 
                   "申万1级", "申万2级", "申万3级", "市盈率ttm", "市净率"]
    
    # 初始化CSV文件（保证表头存在）
    if not os.path.exists(csv_file):
        pd.DataFrame(columns=csv_headers).to_csv(
            csv_file, index=False, encoding='utf-8-sig'
        )
        print(f"📄 初始化CSV文件，表头：{csv_headers}")
    else:
        # 检查表头是否匹配
        try:
            df_check = pd.read_csv(csv_file, nrows=1)
            if list(df_check.columns) != csv_headers:
                df_old = pd.read_csv(csv_file, header=None)
                df_old.columns = csv_headers
                df_old.to_csv(csv_file, index=False, encoding='utf-8-sig')
                print(f"🔧 修复CSV表头为：{csv_headers}")
        except:
            pd.DataFrame(columns=csv_headers).to_csv(
                csv_file, index=False, encoding='utf-8-sig'
            )
            print(f"🔧 重置CSV文件并写入表头：{csv_headers}")
    
    # 记录已抓取的股票代码（去重）
    crawled_codes = set()
    if os.path.exists(csv_file):
        try:
            df_exist = pd.read_csv(csv_file)
            crawled_codes = set(df_exist["代码"].dropna().astype(str).tolist())
        except:
            crawled_codes = set()
    print(f"📌 已抓取过的股票数量：{len(crawled_codes)}")
    
    # 获取所有申万三级行业代码
    third_industry_df = sw_index_third_info()
    third_industry_codes = third_industry_df["行业代码"].tolist()
    print(f"📥 共获取 {len(third_industry_codes)} 个申万三级行业，开始遍历抓取...")
    
    success_count = 0
    total_processed = 0
    
    for i, industry_code in enumerate(third_industry_codes):
        # 抓取该行业下的个股数据
        stock_df = sw_index_third_cons(symbol=industry_code)
        if stock_df.empty:
            time.sleep(0.5)  # 失败时延长等待
            continue
        
        # 遍历该行业下的个股
        for _, row in stock_df.iterrows():
            code = str(row["股票代码"]).strip()
            # 跳过已抓取的股票（去重）
            if code in crawled_codes:
                continue
            
            # 提取核心字段
            name = row["股票简称"]
            current_price = row["价格"]
            market_cap = row["市值"]
            dividend_yield = row["股息率"]
            sw1 = row["申万1级"]
            sw2 = row["申万2级"]
            sw3 = row["申万3级"]
            pe_ttm = row["市盈率ttm"]
            pb = row["市净率"]
            
            # 只保留有股息率且大于0的记录
            if pd.notna(dividend_yield) and dividend_yield > 0:
                single_data = pd.DataFrame({
                    "代码": [code],
                    "名称": [name],
                    "最新价": [current_price],
                    "总市值(亿)": [round(market_cap, 2) if pd.notna(market_cap) else 0],
                    "股息率(%)": [dividend_yield],
                    "申万1级": [sw1],
                    "申万2级": [sw2],
                    "申万3级": [sw3],
                    "市盈率ttm": [pe_ttm],
                    "市净率": [pb]
                })
                # 追加写入CSV
                single_data.to_csv(
                    csv_file,
                    mode='a',
                    index=False,
                    header=False,
                    encoding='utf-8-sig'
                )
                success_count += 1
                crawled_codes.add(code)  # 标记为已抓取
        
        total_processed += 1
        # 打印进度
        if i % 10 == 0:
            print(f"✅ 已处理 {total_processed}/{len(third_industry_codes)} 个行业，新增 {success_count} 支有股息的股票...")
        time.sleep(0.3)  # 防反爬
    
    # 最终排序（按股息率降序）
    if os.path.exists(csv_file) and success_count > 0:
        df_final = pd.read_csv(csv_file)
        df_final = df_final.sort_values(by='股息率(%)', ascending=False).drop_duplicates(subset=["代码"], keep="first")
        df_final.to_csv(csv_file, index=False, encoding='utf-8-sig')
        print(f"\n✨ 任务完成！累计抓取 {len(df_final)} 支有股息的A股（去重后）。")
        print(f"📁 数据已存入 {csv_file}，按股息率降序排列")
    else:
        print("⚠️ 未抓取到有效数据，请检查网络或接口是否正常。")

if __name__ == "__main__":
    fetch_and_save_dividend_data()