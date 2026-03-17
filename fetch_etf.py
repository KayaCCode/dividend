"""
etf_data_fetcher.py
ETF数据获取与存储系统
功能：从多个接口获取ETF数据并保存到CSV文件
"""

import akshare as ak
import pandas as pd
import numpy as np
import os
import time
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List

# 配置日志系统
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/etf_fetcher.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ETFDataFetcher:
    """ETF数据获取与存储类"""
    
    def __init__(self, data_root: str = "data"):
        """
        初始化数据获取器
        
        Parameters:
        -----------
        data_root : str
            数据存储根目录
        """
        self.data_root = data_root
        self._create_directories()
        
        # 常用ETF列表（可根据需要扩展）
        self.common_etfs = {
            '515030': '华夏新能源车ETF',
            '512000': '华宝券商ETF',
            '512880': '国泰证券ETF',
            '512480': '国联安半导体ETF',
            '159995': '华夏芯片ETF',
            '510300': '华泰柏瑞沪深300ETF',
            '510500': '南方中证500ETF',
            '588000': '华安科创50ETF'
        }
        
    def _create_directories(self):
        """创建必要的目录结构"""
        directories = [
            self.data_root,
            f"{self.data_root}/daily",
            f"{self.data_root}/intraday",
            f"{self.data_root}/realtime",
            "logs"
        ]
        
        for directory in directories:
            os.makedirs(directory, exist_ok=True)
            logger.info(f"确保目录存在: {directory}")
    
    def get_daily_data(self, symbol: str, days: int = 365, 
                       adjust: str = 'qfq', save: bool = True) -> Optional[pd.DataFrame]:
        """
        获取ETF日线数据（首选东财接口）
        
        Parameters:
        -----------
        symbol : str
            ETF代码，如 '515030'
        days : int
            获取最近多少天的数据
        adjust : str
            复权方式: 'qfq' (前复权), 'hfq' (后复权), '' (不复权)
        save : bool
            是否保存到CSV文件
        
        Returns:
        --------
        pd.DataFrame or None
        """
        try:
            # 计算日期范围
            end_date = datetime.now().strftime("%Y%m%d")
            start_date = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")
            
            logger.info(f"开始获取 {symbol} 的日线数据，时间范围: {start_date} 到 {end_date}")
            
            # 尝试东财接口（首选）
            try:
                df = ak.fund_etf_hist_em(
                    symbol=symbol,
                    period="daily",
                    start_date=start_date,
                    end_date=end_date,
                    adjust=adjust
                )
                logger.info(f"东财接口成功获取 {symbol} 日线数据 {len(df)} 条")
                
                # 重命名列以保持一致性
                column_mapping = {
                    '日期': 'date',
                    '开盘': 'open',
                    '收盘': 'close',
                    '最高': 'high',
                    '最低': 'low',
                    '成交量': 'volume',
                    '成交额': 'amount',
                    '振幅': 'amplitude',
                    '涨跌幅': 'pct_change',
                    '涨跌额': 'change',
                    '换手率': 'turnover'
                }
                df = df.rename(columns=column_mapping)
                
            except Exception as e1:
                logger.warning(f"东财接口失败: {e1}，尝试备用接口...")
                
                # 备用接口：新浪接口
                try:
                    market_prefix = 'sh' if symbol.startswith('51') else 'sz'
                    df = ak.fund_etf_hist_sina(symbol=f"{market_prefix}{symbol}")
                    logger.info(f"新浪接口成功获取 {symbol} 日线数据 {len(df)} 条")
                    
                    # 新浪接口列名不同
                    df = df.rename(columns={
                        'date': 'date',
                        'open': 'open',
                        'close': 'close',
                        'high': 'high',
                        'low': 'low',
                        'volume': 'volume'
                    })
                    
                except Exception as e2:
                    logger.error(f"所有日线接口均失败: {e2}")
                    return None
            
            # 数据清洗和格式转换
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date').reset_index(drop=True)
            
            # 添加元数据
            df['symbol'] = symbol
            df['data_type'] = 'daily'
            df['fetch_time'] = datetime.now()
            
            # 计算基础技术指标
            df = self._calculate_basic_indicators(df)
            
            if save:
                self._save_to_csv(df, symbol, 'daily')
            
            return df
            
        except Exception as e:
            logger.error(f"获取 {symbol} 日线数据时发生错误: {e}")
            return None
    
    def get_realtime_data(self, symbol: str = None, save: bool = True) -> Optional[pd.DataFrame]:
        """
        获取ETF实时行情数据
        
        Parameters:
        -----------
        symbol : str or None
            指定ETF代码，None表示获取全市场数据
        save : bool
            是否保存到CSV文件
        
        Returns:
        --------
        pd.DataFrame or None
        """
        try:
            logger.info("开始获取ETF实时行情数据...")
            
            # 获取全市场ETF实时行情
            df = ak.fund_etf_spot_em()
            
            # 添加时间戳
            current_time = datetime.now()
            df['fetch_time'] = current_time
            
            if symbol:
                # 获取指定ETF数据
                target_df = df[df['代码'] == symbol].copy()
                if target_df.empty:
                    logger.warning(f"未找到ETF代码: {symbol}")
                    return None
                
                if save:
                    self._save_to_csv(target_df, symbol, 'realtime')
                
                logger.info(f"成功获取 {symbol} 实时数据")
                return target_df
            else:
                # 保存全市场数据
                if save:
                    timestamp = current_time.strftime("%Y%m%d_%H%M%S")
                    filename = f"{self.data_root}/realtime/etf_market_{timestamp}.csv"
                    df.to_csv(filename, index=False, encoding='utf-8-sig')
                    logger.info(f"保存全市场实时数据到: {filename}，共 {len(df)} 条记录")
                
                return df
                
        except Exception as e:
            logger.error(f"获取实时数据时发生错误: {e}")
            return None
    
    def get_intraday_data(self, symbol: str, period: str = '5', 
                          date: str = None, save: bool = True) -> Optional[pd.DataFrame]:
        """
        获取ETF分时数据
        
        Parameters:
        -----------
        symbol : str
            ETF代码，如 '515030'
        period : str
            时间周期: '1', '5', '15', '30', '60' 分钟
        date : str or None
            指定日期（格式: '2025-01-26'），None表示获取最近可用数据
        save : bool
            是否保存到CSV文件
        
        Returns:
        --------
        pd.DataFrame or None
        """
        try:
            # 设置日期范围
            if date:
                # 指定具体日期
                start_date = f"{date} 09:30:00"
                end_date = f"{date} 15:00:00"
            else:
                # 获取最近一个交易日的数据
                today = datetime.now().strftime("%Y-%m-%d")
                start_date = f"{today} 09:30:00"
                end_date = f"{today} 15:00:00"
            
            logger.info(f"开始获取 {symbol} 的 {period} 分钟分时数据")
            
            # 获取分时数据
            df = ak.fund_etf_hist_min_em(
                symbol=f"sh{symbol}",  # 可能需要根据实际情况调整前缀
                period=period,
                adjust="",
                start_date=start_date,
                end_date=end_date
            )
            
            if df.empty:
                logger.warning(f"未获取到 {symbol} 的分时数据")
                return None
            
            # 重命名和清洗
            df = df.rename(columns={'时间': 'datetime'})
            df['datetime'] = pd.to_datetime(df['datetime'])
            
            # 添加元数据
            df['symbol'] = symbol
            df['period'] = f"{period}min"
            df['fetch_time'] = datetime.now()
            
            # 计算额外指标
            df['vwap'] = df['成交额'] / df['成交量'].replace(0, np.nan)
            
            if save:
                date_str = date if date else datetime.now().strftime("%Y%m%d")
                filename = f"{symbol}_{date_str}_{period}min.csv"
                self._save_to_csv(df, filename, 'intraday')
            
            logger.info(f"成功获取 {symbol} 分时数据 {len(df)} 条")
            return df
            
        except Exception as e:
            logger.error(f"获取 {symbol} 分时数据时发生错误: {e}")
            return None
    
    def _calculate_basic_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算基础技术指标"""
        if df.empty:
            return df
        
        try:
            # 确保数据按日期排序
            df = df.sort_values('date').copy()
            
            # 计算移动平均线
            df['ma5'] = df['close'].rolling(window=5).mean()
            df['ma10'] = df['close'].rolling(window=10).mean()
            df['ma20'] = df['close'].rolling(window=20).mean()
            df['ma60'] = df['close'].rolling(window=60).mean()
            
            # 计算MACD
            exp1 = df['close'].ewm(span=12, adjust=False).mean()
            exp2 = df['close'].ewm(span=26, adjust=False).mean()
            df['macd_dif'] = exp1 - exp2
            df['macd_dea'] = df['macd_dif'].ewm(span=9, adjust=False).mean()
            df['macd'] = 2 * (df['macd_dif'] - df['macd_dea'])
            
            # 计算KDJ
            low_min = df['low'].rolling(window=9, min_periods=1).min()
            high_max = df['high'].rolling(window=9, min_periods=1).max()
            rsv = (df['close'] - low_min) / (high_max - low_min + 1e-9) * 100
            df['kdj_k'] = rsv.ewm(alpha=1/3, adjust=False).mean()
            df['kdj_d'] = df['kdj_k'].ewm(alpha=1/3, adjust=False).mean()
            df['kdj_j'] = 3 * df['kdj_k'] - 2 * df['kdj_d']
            
            # 计算ATR（真实波动幅度均值）
            hl = df['high'] - df['low']
            hc = abs(df['high'] - df['close'].shift(1))
            lc = abs(df['low'] - df['close'].shift(1))
            df['tr'] = np.maximum(np.maximum(hl, hc), lc)
            df['atr'] = df['tr'].rolling(window=14).mean()
            df['atr_pct'] = (df['atr'] / df['close']) * 100
            
            # 计算布林带
            df['bb_middle'] = df['close'].rolling(window=20).mean()
            bb_std = df['close'].rolling(window=20).std()
            df['bb_upper'] = df['bb_middle'] + 2 * bb_std
            df['bb_lower'] = df['bb_middle'] - 2 * bb_std
            df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle'] * 100
            
            logger.debug("技术指标计算完成")
            return df
            
        except Exception as e:
            logger.warning(f"计算技术指标时出错: {e}")
            return df
    
    def _save_to_csv(self, df: pd.DataFrame, identifier: str, data_type: str):
        """
        保存DataFrame到CSV文件
        
        Parameters:
        -----------
        df : pd.DataFrame
            要保存的数据
        identifier : str
            标识符（ETF代码或文件名）
        data_type : str
            数据类型: 'daily', 'intraday', 'realtime'
        """
        try:
            # 创建文件名
            timestamp = datetime.now().strftime("%Y%m%d")
            
            if data_type == 'daily':
                filename = f"{self.data_root}/daily/{identifier}_{timestamp}.csv"
            elif data_type == 'intraday':
                # identifier已经是完整文件名
                filename = f"{self.data_root}/intraday/{identifier}"
            elif data_type == 'realtime':
                filename = f"{self.data_root}/realtime/{identifier}_{timestamp}.csv"
            else:
                filename = f"{self.data_root}/{identifier}_{data_type}_{timestamp}.csv"
            
            # 保存到CSV（使用utf-8-sig编码以支持中文）
            df.to_csv(filename, index=False, encoding='utf-8-sig')
            logger.info(f"数据已保存到: {filename} ({len(df)} 条记录)")
            
        except Exception as e:
            logger.error(f"保存数据到CSV时出错: {e}")
    
    def batch_fetch_common_etfs(self, data_types: List[str] = ['daily', 'realtime']):
        """
        批量获取常用ETF数据
        
        Parameters:
        -----------
        data_types : list
            要获取的数据类型列表
        """
        logger.info(f"开始批量获取 {len(self.common_etfs)} 个常用ETF数据")
        
        results = {}
        for symbol, name in self.common_etfs.items():
            logger.info(f"处理 {symbol} ({name})")
            
            symbol_results = {}
            
            if 'daily' in data_types:
                daily_data = self.get_daily_data(symbol, days=180, save=True)
                symbol_results['daily'] = daily_data is not None
            
            if 'realtime' in data_types:
                realtime_data = self.get_realtime_data(symbol, save=True)
                symbol_results['realtime'] = realtime_data is not None
            
            results[symbol] = symbol_results
            
            # 避免请求过快
            time.sleep(1)
        
        # 汇总报告
        success_counts = {
            'daily': sum(1 for r in results.values() if r.get('daily', False)),
            'realtime': sum(1 for r in results.values() if r.get('realtime', False))
        }
        
        logger.info(f"批量获取完成: 日线数据 {success_counts['daily']}/{len(results)}，"
                   f"实时数据 {success_counts['realtime']}/{len(results)}")
        
        return results
    
    def generate_data_summary(self):
        """生成数据摘要报告"""
        summary = {
            'data_root': self.data_root,
            'daily_files': [],
            'intraday_files': [],
            'realtime_files': [],
            'total_size_mb': 0
        }
        
        # 扫描各目录
        for data_type in ['daily', 'intraday', 'realtime']:
            dir_path = f"{self.data_root}/{data_type}"
            if os.path.exists(dir_path):
                files = os.listdir(dir_path)
                csv_files = [f for f in files if f.endswith('.csv')]
                summary[f'{data_type}_files'] = csv_files
                
                # 计算总大小
                for file in csv_files:
                    file_path = os.path.join(dir_path, file)
                    summary['total_size_mb'] += os.path.getsize(file_path) / (1024 * 1024)
        
        # 保存摘要报告
        summary_df = pd.DataFrame([{
            'timestamp': datetime.now(),
            'daily_files_count': len(summary['daily_files']),
            'intraday_files_count': len(summary['intraday_files']),
            'realtime_files_count': len(summary['realtime_files']),
            'total_size_mb': round(summary['total_size_mb'], 2)
        }])
        
        summary_file = f"{self.data_root}/data_summary.csv"
        if os.path.exists(summary_file):
            existing_df = pd.read_csv(summary_file)
            summary_df = pd.concat([existing_df, summary_df], ignore_index=True)
        
        summary_df.to_csv(summary_file, index=False, encoding='utf-8-sig')
        
        logger.info(f"数据摘要: {len(summary['daily_files'])} 个日线文件，"
                   f"{len(summary['realtime_files'])} 个实时文件，"
                   f"总大小 {summary['total_size_mb']:.2f} MB")
        
        return summary


# 使用示例
def main():
    """主函数：演示如何使用ETFDataFetcher"""
    
    # 创建数据获取器实例
    fetcher = ETFDataFetcher(data_root="etf_data")
    
    print("=" * 60)
    print("ETF数据获取与存储系统")
    print("=" * 60)
    
    # 示例1：获取单个ETF的日线数据（如515030）
    print("\n1. 获取515030（新能源车ETF）的日线数据...")
    df_515030 = fetcher.get_daily_data('515030', days=300, save=True)
    
    if df_515030 is not None and not df_515030.empty:
        print(f"  获取成功！最新数据：")
        print(f"  日期: {df_515030.iloc[-1]['date'].date()}")
        print(f"  收盘价: {df_515030.iloc[-1]['close']:.3f}")
        print(f"  涨跌幅: {df_515030.iloc[-1]['pct_change']:.2f}%")
        print(f"  成交量: {df_515030.iloc[-1]['volume']:,.0f}")
        print(f"  MA5: {df_515030.iloc[-1]['ma5']:.3f}")
        print(f"  MA20: {df_515030.iloc[-1]['ma20']:.3f}")
        print(f"  MACD: {df_515030.iloc[-1]['macd']:.4f}")
        print(f"  KDJ_K: {df_515030.iloc[-1]['kdj_k']:.1f}")
        print(f"  ATR%: {df_515030.iloc[-1]['atr_pct']:.2f}%")
    
    # 示例2：获取实时行情数据
    print("\n2. 获取515030的实时行情数据...")
    realtime_data = fetcher.get_realtime_data('515030', save=True)
    if realtime_data is not None and not realtime_data.empty:
        print(f"  实时数据获取成功！")
        print(f"  最新价: {realtime_data.iloc[0]['最新价']}")
        print(f"  涨跌幅: {realtime_data.iloc[0]['涨跌幅']}%")
        print(f"  成交量: {realtime_data.iloc[0]['成交量']}")
        print(f"  主力净流入: {realtime_data.iloc[0]['主力净流入-净额']:,.0f}")
    
    # 示例3：获取分时数据（可选）
    # print("\n3. 获取515030的5分钟分时数据...")
    # intraday_data = fetcher.get_intraday_data('515030', period='5', save=True)
    # if intraday_data is not None:
    #     print(f"  分时数据获取成功！共 {len(intraday_data)} 条记录")
    
    # 示例4：批量获取常用ETF数据
    print("\n4. 批量获取常用ETF数据...")
    batch_results = fetcher.batch_fetch_common_etfs(data_types=['daily', 'realtime'])
    
    # 示例5：生成数据摘要
    print("\n5. 生成数据摘要报告...")
    summary = fetcher.generate_data_summary()
    
    print("\n" + "=" * 60)
    print("数据获取完成！")
    print(f"数据存储位置: {os.path.abspath(fetcher.data_root)}")
    print("=" * 60)


if __name__ == "__main__":
    # 运行主函数
    main()