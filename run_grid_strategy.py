#!/usr/bin/env python3
"""
启动脚本
运行：streamlit run run_grid_strategy.py
"""

import subprocess
import sys

def main():
    """启动Streamlit应用"""
    try:
        # 检查依赖
        print("正在启动网格策略筛选系统...")
        print("请确保已安装以下依赖：")
        print("1. akshare")
        print("2. pandas")
        print("3. numpy")
        print("4. plotly")
        print("5. streamlit")
        print("\n如果需要TA-Lib技术指标，请单独安装TA-Lib")
        
        # 启动Streamlit
        subprocess.run([sys.executable, "-m", "streamlit", "run", "grid_strategy_system.py"])
        
    except KeyboardInterrupt:
        print("\n程序已终止")
    except Exception as e:
        print(f"启动失败: {e}")

if __name__ == "__main__":
    main()