import akshare as ak

def get_all_a_stock_codes():
    """
    获取A股所有股票的代码和基本信息
    返回：DataFrame格式，包含股票代码、名称、交易所等信息
    """
    try:
        # 获取全市场股票列表（包含A股、港股、美股等）
        stock_info_df = ak.stock_info_a_code_name()
        
        # 筛选A股代码（A股代码规则：6位数字，沪A60开头、深A00/30开头、北交所8开头）
        # 定义A股代码的正则匹配规则
        a_stock_pattern = r'^(60|00|30|8)[0-9]{4}$'
        a_stock_df = stock_info_df[stock_info_df['code'].str.match(a_stock_pattern)]
        
        # 重置索引，方便查看
        a_stock_df = a_stock_df.reset_index(drop=True)
        
        return a_stock_df
    
    except Exception as e:
        print(f"获取数据失败：{e}")
        return None

if __name__ == "__main__":
    # 调用函数获取A股股票代码
    a_stock_codes = get_all_a_stock_codes()
    
    if a_stock_codes is not None:
        # 打印前10条数据，查看格式
        print("A股股票代码（前10条）：")
        print(a_stock_codes.head(10))
        
        # 提取仅股票代码的列表
        code_list = a_stock_codes['code'].tolist()
        print(f"\nA股股票总数：{len(code_list)}")
        print(f"股票代码列表示例：{code_list[:5]}")
        
        # 可选：将数据保存为CSV文件，方便后续使用
        a_stock_codes.to_csv("a_stock_codes.csv", index=False, encoding="utf-8")
        print("\n数据已保存为 a_stock_codes.csv 文件")