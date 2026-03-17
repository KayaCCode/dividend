"""
grid_strategy_system.py
完整的网格策略筛选系统
包含ADX指标和Streamlit可视化界面
"""

import akshare as ak
import pandas as pd
import numpy as np
import warnings
import os
import json
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, asdict
import streamlit as st
from streamlit_option_menu import option_menu

# 尝试导入TA-Lib，如果不可用则使用备选方案
try:
    import talib
    TALIB_AVAILABLE = True
except ImportError:
    TALIB_AVAILABLE = False
    print("TA-Lib未安装，将使用备选技术指标计算方法")

warnings.filterwarnings('ignore')

@dataclass
class ETFGridParameters:
    """网格交易参数数据类"""
    symbol: str
    name: str
    current_price: float
    score: float
    
    # 震荡区间参数
    upper_bound: float
    lower_bound: float
    box_height_pct: float
    
    # 网格参数
    grid_spacing_pct: float
    grid_spacing_price: float
    grid_layers: int
    
    # 仓位参数
    total_allocation: float
    grid_amount_per_layer: float
    initial_position_pct: float
    initial_position_amount: float
    
    # 风险参数
    stop_loss_price: float
    trailing_stop_pct: float
    
    # 技术指标
    atr_pct: float
    cross_count: int
    ma20_deviation: float  # 价格与20日均线的平均偏离度
    adx: float  # ADX指标
    liquidity_score: float
    
    # 状态
    in_box_position: str

class GridStrategySystem:
    """网格策略系统"""
    
    def __init__(self, capital: float = 100000):
        """
        初始化网格策略系统
        
        Parameters:
        ----------
        capital : float
            总资金量，用于计算仓位分配
        """
        self.capital = capital
        self.watch_list = self._get_default_watch_list()
        
        # 指标权重配置
        self.weights = {
            'atr_pct': 0.20,        # 波动率权重
            'cross_count': 0.25,    # 震荡频率权重
            'ma20_deviation': 0.15, # 平均偏离度权重（反向）
            'adx': 0.20,            # ADX权重（反向）
            'liquidity': 0.10,      # 流动性权重
            'box_quality': 0.10     # 箱体质量权重
        }
        
        # 网格参数配置
        self.grid_config = {
            'min_layers': 5,
            'max_layers': 12,
            'min_spacing_pct': 1.2,
            'max_spacing_pct': 4.0,
            'max_allocation_pct': 0.20,
            'initial_position_pct': 0.3,
            'stop_loss_pct': 0.08,
            'trailing_stop_pct': 0.05
        }
    
    def _get_default_watch_list(self) -> Dict:
        """获取默认观察列表"""
        return {
            '512000': '券商ETF',
            '512880': '证券ETF',
            '512480': '半导体ETF',
            '159995': '芯片ETF',
            '515000': '科技ETF',
            '512400': '有色金属ETF',
            '510300': '沪深300ETF',
            '510500': '中证500ETF',
            '588000': '科创50ETF',
            '159915': '创业板ETF',
            '512800': '银行ETF',
            '512660': '军工ETF',
            '512010': '医药ETF',
            '512170': '医疗ETF',
            '515790': '光伏ETF',
            '512200': '房地产ETF',
            '512980': '传媒ETF',
            '515050': '5GETF',
            '515880': '通信ETF',
            '512000': '券商ETF'
        }
    
    def fetch_etf_data(self, symbol: str, days: int = 90) -> Optional[pd.DataFrame]:
        """
        获取ETF历史数据并计算技术指标
        """
        try:
            end_date = datetime.now().strftime("%Y%m%d")
            start_date = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")
            
            # 尝试东财接口
            df = None
            try:
                df = ak.fund_etf_hist_em(
                    symbol=symbol,
                    period="daily",
                    start_date=start_date,
                    end_date=end_date,
                    adjust="qfq"
                )
                if df is not None and not df.empty:
                    column_mapping = {
                        '日期': 'date', '开盘': 'open', '收盘': 'close',
                        '最高': 'high', '最低': 'low', '成交量': 'volume',
                        '成交额': 'amount', '涨跌幅': 'pct_change'
                    }
                    df = df.rename(columns=column_mapping)
            except:
                pass
            
            # 如果东财接口失败，尝试新浪接口
            if df is None or df.empty:
                try:
                    market_prefix = 'sh' if symbol.startswith('51') or symbol.startswith('58') else 'sz'
                    df = ak.fund_etf_hist_sina(symbol=f"{market_prefix}{symbol}")
                except:
                    return None
            
            if df is None or df.empty:
                return None
            
            # 数据清洗和格式转换
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date').reset_index(drop=True)
            
            # 确保有足够的数据
            if len(df) < 30:
                return None
            
            # 计算技术指标
            return self._calculate_technical_indicators(df)
            
        except Exception as e:
            st.error(f"获取 {symbol} 数据失败: {e}")
            return None
    
    def _calculate_technical_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        计算技术指标，包括ADX和平均偏离度
        """
        df = df.copy()
        
        # 1. 基础指标
        df['ma5'] = df['close'].rolling(window=5).mean()
        df['ma10'] = df['close'].rolling(window=10).mean()
        df['ma20'] = df['close'].rolling(window=20).mean()
        df['ma60'] = df['close'].rolling(window=60).mean()
        
        # 2. 计算ATR
        high_low = df['high'] - df['low']
        high_close = abs(df['high'] - df['close'].shift(1))
        low_close = abs(df['low'] - df['close'].shift(1))
        df['tr'] = np.maximum(np.maximum(high_low, high_close), low_close)
        df['atr'] = df['tr'].rolling(window=14).mean()
        df['atr_pct'] = (df['atr'] / df['close']) * 100
        
        # 3. 计算20日穿越信号
        df['above_ma20'] = df['close'] > df['ma20']
        df['cross_signal'] = (df['above_ma20'] != df['above_ma20'].shift(1)).astype(int)
        
        # 4. 计算价格与20日均线的偏离度
        df['ma20_deviation'] = abs(df['close'] - df['ma20']) / df['ma20'] * 100
        
        # 5. 计算ADX指标
        if TALIB_AVAILABLE and len(df) >= 14:
            try:
                df['adx'] = talib.ADX(df['high'].values, df['low'].values, df['close'].values, timeperiod=14)
                df['plus_di'] = talib.PLUS_DI(df['high'].values, df['low'].values, df['close'].values, timeperiod=14)
                df['minus_di'] = talib.MINUS_DI(df['high'].values, df['low'].values, df['close'].values, timeperiod=14)
            except:
                df['adx'] = np.nan
                df['plus_di'] = np.nan
                df['minus_di'] = np.nan
        else:
            # 备选ADX计算方法
            df['adx'] = self._calculate_adx_alternative(df)
        
        # 6. 布林带
        df['bb_middle'] = df['close'].rolling(window=20).mean()
        bb_std = df['close'].rolling(window=20).std()
        df['bb_upper'] = df['bb_middle'] + 2 * bb_std
        df['bb_lower'] = df['bb_middle'] - 2 * bb_std
        df['bb_width_pct'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle'] * 100
        
        # 7. 成交量指标
        df['volume_ma20'] = df['volume'].rolling(window=20).mean()
        df['volume_ratio'] = df['volume'] / df['volume_ma20']
        
        return df
    
    def _calculate_adx_alternative(self, df: pd.DataFrame) -> pd.Series:
        """
        备选ADX计算方法
        """
        # 简化的ADX计算
        tr = df['tr'].copy()
        atr = tr.rolling(window=14).mean()
        
        # 计算方向移动
        up_move = df['high'] - df['high'].shift(1)
        down_move = df['low'].shift(1) - df['low']
        
        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)
        
        # 平滑方向指标
        plus_di = 100 * (pd.Series(plus_dm).rolling(window=14).mean() / atr)
        minus_di = 100 * (pd.Series(minus_dm).rolling(window=14).mean() / atr)
        
        # 计算方向指标差值
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        
        # 计算ADX
        adx = dx.rolling(window=14).mean()
        
        return adx
    
    def calculate_etf_metrics(self, df: pd.DataFrame, symbol: str) -> Dict:
        """
        计算ETF的各项指标
        """
        if df is None or df.empty:
            return None
        
        # 使用最近60个交易日的数据
        recent_df = df.tail(60).copy()
        metrics = {'symbol': symbol}
        
        # 1. 波动率指标
        metrics['atr_pct_avg'] = recent_df['atr_pct'].mean()
        metrics['atr_pct_recent'] = recent_df['atr_pct'].iloc[-1]
        
        # 2. 震荡频率指标
        recent_20 = recent_df.tail(20)
        cross_up = ((recent_20['close'] > recent_20['ma20']) & 
                   (recent_20['close'].shift(1) <= recent_20['ma20'].shift(1))).sum()
        cross_down = ((recent_20['close'] < recent_20['ma20']) & 
                     (recent_20['close'].shift(1) >= recent_20['ma20'].shift(1))).sum()
        metrics['cross_count_20'] = int(cross_up + cross_down)
        
        # 3. 平均偏离度指标
        metrics['ma20_deviation_avg'] = recent_df['ma20_deviation'].mean()
        
        # 4. ADX指标
        metrics['adx_avg'] = recent_df['adx'].mean()
        metrics['adx_recent'] = recent_df['adx'].iloc[-1]
        
        # 5. 流动性指标
        metrics['avg_amount'] = recent_df['amount'].mean() / 10000
        
        # 6. 箱体识别
        box_metrics = self._identify_box_range(recent_df)
        metrics.update(box_metrics)
        
        # 7. 当前状态
        current_price = recent_df['close'].iloc[-1]
        metrics['current_price'] = current_price
        metrics['in_box_position'] = self._get_box_position(
            current_price, metrics['box_upper'], metrics['box_lower']
        )
        
        return metrics
    
    def _identify_box_range(self, df: pd.DataFrame) -> Dict:
        """
        识别箱体震荡区间
        """
        recent_40 = df.tail(40).copy()
        
        # 多种方法确定箱体
        # 方法1：价格高低点
        price_high = recent_40['high'].max()
        price_low = recent_40['low'].min()
        
        # 方法2：布林带
        bb_upper = recent_40['bb_upper'].mean()
        bb_lower = recent_40['bb_lower'].mean()
        
        # 方法3：移动平均线通道
        ma_upper = recent_40['ma20'].max()
        ma_lower = recent_40['ma20'].min()
        
        # 综合确定箱体
        box_upper = min(price_high, bb_upper, ma_upper)
        box_lower = max(price_low, bb_lower, ma_lower)
        
        # 确保箱体有足够高度
        min_height = recent_40['close'].mean() * 0.08  # 至少8%
        if (box_upper - box_lower) < min_height:
            box_upper = recent_40['close'].mean() + min_height / 2
            box_lower = recent_40['close'].mean() - min_height / 2
        
        current_price = recent_40['close'].iloc[-1]
        
        # 计算箱体质量
        in_box_days = ((recent_40['close'] >= box_lower) & 
                      (recent_40['close'] <= box_upper)).sum()
        box_quality_score = in_box_days / len(recent_40)
        
        return {
            'box_upper': round(box_upper, 4),
            'box_lower': round(box_lower, 4),
            'box_height': round(box_upper - box_lower, 4),
            'box_height_pct': round((box_upper - box_lower) / current_price * 100, 2),
            'box_quality': round(box_quality_score, 3)
        }
    
    def _get_box_position(self, price: float, upper: float, lower: float) -> str:
        """
        判断价格在箱体中的位置
        """
        box_range = upper - lower
        if box_range <= 0:
            return 'unknown'
        
        position_ratio = (price - lower) / box_range
        
        if position_ratio > 0.66:
            return 'upper'
        elif position_ratio < 0.33:
            return 'lower'
        else:
            return 'middle'
    
    def score_etf_metrics(self, metrics: Dict) -> Dict:
        """
        对ETF指标进行评分
        """
        scores = {}
        
        # 1. 波动率得分
        atr_pct = metrics['atr_pct_recent']
        if atr_pct >= 3.5:
            scores['atr_score'] = 100
        elif atr_pct <= 1.5:
            scores['atr_score'] = 30
        else:
            scores['atr_score'] = 30 + (atr_pct - 1.5) * (70 / 2.0)
        
        # 2. 震荡频率得分
        cross_count = metrics['cross_count_20']
        if cross_count >= 6:
            scores['cross_score'] = 100
        elif cross_count <= 1:
            scores['cross_score'] = 20
        else:
            scores['cross_score'] = 20 + (cross_count - 1) * (80 / 5.0)
        
        # 3. 平均偏离度得分（反向）
        deviation = metrics['ma20_deviation_avg']
        if deviation <= 1.0:
            scores['deviation_score'] = 100  # 偏离度小，趋势弱
        elif deviation >= 5.0:
            scores['deviation_score'] = 20   # 偏离度大，趋势强
        else:
            scores['deviation_score'] = 100 - (deviation - 1.0) * (80 / 4.0)
        
        # 4. ADX得分（反向）
        adx = metrics['adx_avg']
        if adx <= 20:
            scores['adx_score'] = 100  # ADX低，趋势弱
        elif adx >= 40:
            scores['adx_score'] = 20   # ADX高，趋势强
        else:
            scores['adx_score'] = 100 - (adx - 20) * (80 / 20.0)
        
        # 5. 流动性得分
        avg_amount = metrics['avg_amount']
        if avg_amount >= 50000:
            scores['liquidity_score'] = 100
        elif avg_amount <= 5000:
            scores['liquidity_score'] = 30
        else:
            scores['liquidity_score'] = 30 + (avg_amount - 5000) * (70 / 45000)
        
        # 6. 箱体质量得分
        box_quality = metrics['box_quality']
        scores['box_quality_score'] = box_quality * 100
        
        # 计算综合得分
        total_score = 0
        for key, weight in self.weights.items():
            if key == 'ma20_deviation':
                score_key = 'deviation_score'
            elif key == 'adx':
                score_key = 'adx_score'
            else:
                score_key = f"{key}_score"
            
            total_score += scores.get(score_key, 50) * weight
        
        scores['total_score'] = round(total_score, 1)
        
        # 将分数添加到指标中
        metrics.update(scores)
        metrics['liquidity_score'] = scores['liquidity_score']
        
        return metrics
    
    def calculate_grid_parameters(self, metrics: Dict) -> Optional[ETFGridParameters]:
        """
        计算网格交易参数
        """
        try:
            symbol = metrics['symbol']
            name = self.watch_list.get(symbol, symbol)
            
            # 基础价格信息
            current_price = metrics['current_price']
            box_upper = metrics['box_upper']
            box_lower = metrics['box_lower']
            box_height_pct = metrics['box_height_pct']
            
            # 1. 确定网格间距
            atr_pct = metrics['atr_pct_recent']
            base_spacing = atr_pct * 1.2
            grid_spacing_pct = max(
                self.grid_config['min_spacing_pct'],
                min(self.grid_config['max_spacing_pct'], base_spacing)
            )
            grid_spacing_price = current_price * grid_spacing_pct / 100
            
            # 2. 确定网格层数
            box_height_price = box_upper - box_lower
            theoretical_layers = box_height_price / grid_spacing_price
            grid_layers = int(max(
                self.grid_config['min_layers'],
                min(self.grid_config['max_layers'], theoretical_layers)
            ))
            
            # 3. 资金分配
            max_allocation = self.capital * self.grid_config['max_allocation_pct']
            total_allocation = max_allocation * (metrics['total_score'] / 100)
            
            # 4. 每层金额和初始仓位
            grid_amount_per_layer = total_allocation / grid_layers
            initial_position_pct = self.grid_config['initial_position_pct']
            initial_position_amount = total_allocation * initial_position_pct
            
            # 5. 风险控制参数
            stop_loss_price = current_price * (1 - self.grid_config['stop_loss_pct'])
            
            # 6. 确定当前位置
            in_box_position = metrics['in_box_position']
            
            return ETFGridParameters(
                symbol=symbol,
                name=name,
                current_price=current_price,
                score=metrics['total_score'],
                upper_bound=box_upper,
                lower_bound=box_lower,
                box_height_pct=box_height_pct,
                grid_spacing_pct=grid_spacing_pct,
                grid_spacing_price=grid_spacing_price,
                grid_layers=grid_layers,
                total_allocation=total_allocation,
                grid_amount_per_layer=grid_amount_per_layer,
                initial_position_pct=initial_position_pct,
                initial_position_amount=initial_position_amount,
                stop_loss_price=stop_loss_price,
                trailing_stop_pct=self.grid_config['trailing_stop_pct'],
                atr_pct=atr_pct,
                cross_count=metrics['cross_count_20'],
                ma20_deviation=metrics['ma20_deviation_avg'],
                adx=metrics['adx_avg'],
                liquidity_score=metrics['liquidity_score'],
                in_box_position=in_box_position
            )
        except Exception as e:
            st.error(f"计算 {metrics.get('symbol', '未知')} 网格参数失败: {e}")
            return None
    
    def screen_etfs_for_grid(self, top_n: int = 5) -> List[ETFGridParameters]:
        """
        筛选适合网格交易的ETF
        """
        st.info(f"开始筛选适合网格交易的ETF，共 {len(self.watch_list)} 个标的...")
        
        all_metrics = []
        grid_params_list = []
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for idx, (symbol, name) in enumerate(self.watch_list.items()):
            progress = (idx + 1) / len(self.watch_list)
            progress_bar.progress(progress)
            status_text.text(f"正在分析 {symbol} ({name})...")
            
            # 获取数据
            df = self.fetch_etf_data(symbol, days=90)
            if df is None or df.empty:
                continue
            
            # 计算指标
            metrics = self.calculate_etf_metrics(df, symbol)
            if metrics is None:
                continue
            
            # 评分
            scored_metrics = self.score_etf_metrics(metrics)
            
            # 计算网格参数
            grid_params = self.calculate_grid_parameters(scored_metrics)
            if grid_params is None:
                continue
            
            all_metrics.append(scored_metrics)
            grid_params_list.append(grid_params)
        
        progress_bar.empty()
        status_text.empty()
        
        # 按总分排序
        grid_params_list.sort(key=lambda x: x.score, reverse=True)
        
        return grid_params_list[:top_n]
    
    def create_price_chart(self, symbol: str, df: pd.DataFrame, 
                          grid_params: ETFGridParameters = None) -> go.Figure:
        """
        创建价格图表
        """
        fig = go.Figure()
        
        # 价格线
        fig.add_trace(go.Scatter(
            x=df['date'],
            y=df['close'],
            mode='lines',
            name='收盘价',
            line=dict(color='blue', width=2)
        ))
        
        # 移动平均线
        fig.add_trace(go.Scatter(
            x=df['date'],
            y=df['ma20'],
            mode='lines',
            name='20日均线',
            line=dict(color='orange', width=1.5, dash='dash')
        ))
        
        # 如果提供了网格参数，添加箱体和网格线
        if grid_params:
            # 箱体上轨
            fig.add_hline(
                y=grid_params.upper_bound,
                line_dash="dash",
                line_color="red",
                opacity=0.5,
                annotation_text=f"箱体上轨: {grid_params.upper_bound:.3f}"
            )
            
            # 箱体下轨
            fig.add_hline(
                y=grid_params.lower_bound,
                line_dash="dash",
                line_color="green",
                opacity=0.5,
                annotation_text=f"箱体下轨: {grid_params.lower_bound:.3f}"
            )
            
            # 网格线
            center_price = grid_params.current_price
            for i in range(1, grid_params.grid_layers//2 + 2):
                # 向上网格
                sell_price = center_price * (1 + i * grid_params.grid_spacing_pct / 100)
                if sell_price <= grid_params.upper_bound:
                    fig.add_hline(
                        y=sell_price,
                        line_dash="dot",
                        line_color="darkred",
                        opacity=0.3,
                        annotation_text=f"卖{i}: {sell_price:.3f}"
                    )
                
                # 向下网格
                buy_price = center_price * (1 - i * grid_params.grid_spacing_pct / 100)
                if buy_price >= grid_params.lower_bound:
                    fig.add_hline(
                        y=buy_price,
                        line_dash="dot",
                        line_color="darkgreen",
                        opacity=0.3,
                        annotation_text=f"买{i}: {buy_price:.3f}"
                    )
        
        fig.update_layout(
            title=f"{symbol} 价格走势与技术分析",
            xaxis_title="日期",
            yaxis_title="价格 (元)",
            hovermode="x unified",
            height=500
        )
        
        return fig
    
    def create_technical_chart(self, df: pd.DataFrame) -> go.Figure:
        """
        创建技术指标图表
        """
        fig = go.Figure()
        
        # ADX指标
        fig.add_trace(go.Scatter(
            x=df['date'],
            y=df['adx'],
            mode='lines',
            name='ADX',
            line=dict(color='purple', width=2),
            yaxis="y2"
        ))
        
        # 正负DI指标
        if 'plus_di' in df.columns and 'minus_di' in df.columns:
            fig.add_trace(go.Scatter(
                x=df['date'],
                y=df['plus_di'],
                mode='lines',
                name='+DI',
                line=dict(color='green', width=1),
                yaxis="y2"
            ))
            fig.add_trace(go.Scatter(
                x=df['date'],
                y=df['minus_di'],
                mode='lines',
                name='-DI',
                line=dict(color='red', width=1),
                yaxis="y2"
            ))
        
        # ATR指标
        fig.add_trace(go.Scatter(
            x=df['date'],
            y=df['atr_pct'],
            mode='lines',
            name='ATR%',
            line=dict(color='orange', width=2),
            yaxis="y3"
        ))
        
        fig.update_layout(
            title="技术指标分析",
            xaxis_title="日期",
            yaxis_title="ADX/DI",
            yaxis2=dict(
                title="ATR%",
                overlaying="y",
                side="right"
            ),
            yaxis3=dict(
                title="ATR%",
                overlaying="y",
                side="right",
                position=0.95
            ),
            hovermode="x unified",
            height=400
        )
        
        return fig


def create_streamlit_app():
    """创建Streamlit应用"""
    st.set_page_config(
        page_title="A股网格策略筛选系统",
        page_icon="📈",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # 自定义CSS
    st.markdown("""
    <style>
    .main-header {
        font-size: 2.5rem;
        color: #1E88E5;
        text-align: center;
        margin-bottom: 2rem;
    }
    .sub-header {
        font-size: 1.5rem;
        color: #424242;
        margin-top: 1.5rem;
        margin-bottom: 1rem;
    }
    .metric-card {
        background-color: #f5f5f5;
        padding: 1rem;
        border-radius: 10px;
        margin-bottom: 1rem;
        border-left: 5px solid #1E88E5;
    }
    .grid-params {
        background-color: #E3F2FD;
        padding: 1rem;
        border-radius: 10px;
        margin-bottom: 1rem;
    }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown('<h1 class="main-header">📊 A股网格策略筛选系统</h1>', unsafe_allow_html=True)
    
    # 侧边栏配置
    with st.sidebar:
        st.markdown("## ⚙️ 参数配置")
        
        # 资金配置
        capital = st.number_input(
            "总资金量 (元)",
            min_value=10000,
            max_value=1000000,
            value=100000,
            step=10000
        )
        
        # 筛选数量
        top_n = st.slider(
            "筛选数量",
            min_value=1,
            max_value=10,
            value=5
        )
        
        # ETF选择
        st.markdown("### 📋 观察池配置")
        watch_list_options = {
            '512000': '券商ETF',
            '512880': '证券ETF',
            '512480': '半导体ETF',
            '159995': '芯片ETF',
            '510300': '沪深300ETF',
            '510500': '中证500ETF',
            '588000': '科创50ETF'
        }
        
        selected_etfs = st.multiselect(
            "选择ETF观察池",
            options=list(watch_list_options.keys()),
            format_func=lambda x: f"{x} - {watch_list_options[x]}",
            default=['512000', '512880', '512480', '510300']
        )
        
        # 网格参数配置
        st.markdown("### ⚙️ 网格参数")
        min_spacing = st.slider("最小网格间距(%)", 0.5, 3.0, 1.2, 0.1)
        max_spacing = st.slider("最大网格间距(%)", 2.0, 6.0, 4.0, 0.1)
        max_allocation = st.slider("单个标的仓位上限(%)", 5, 50, 20, 5)
        
        # 开始筛选按钮
        if st.button("🚀 开始筛选", type="primary", use_container_width=True):
            st.session_state['run_screening'] = True
        else:
            if 'run_screening' not in st.session_state:
                st.session_state['run_screening'] = False
    
    # 主内容区
    if st.session_state['run_screening']:
        # 初始化系统
        system = GridStrategySystem(capital=capital)
        
        # 更新观察列表
        custom_watch_list = {}
        for etf in selected_etfs:
            if etf in watch_list_options:
                custom_watch_list[etf] = watch_list_options[etf]
        system.watch_list = custom_watch_list
        
        # 更新网格参数
        system.grid_config['min_spacing_pct'] = min_spacing
        system.grid_config['max_spacing_pct'] = max_spacing
        system.grid_config['max_allocation_pct'] = max_allocation / 100
        
        # 执行筛选
        with st.spinner("正在筛选适合网格交易的ETF..."):
            grid_params_list = system.screen_etfs_for_grid(top_n=top_n)
        
        if not grid_params_list:
            st.error("未找到符合条件的ETF，请调整参数重试。")
            return
        
        # 显示筛选结果摘要
        st.markdown('<h2 class="sub-header">📋 筛选结果摘要</h2>', unsafe_allow_html=True)
        
        # 创建摘要表格
        summary_data = []
        for params in grid_params_list:
            summary_data.append({
                '排名': len(summary_data) + 1,
                '代码': params.symbol,
                '名称': params.name,
                '综合得分': params.score,
                '当前价格': f"¥{params.current_price:.3f}",
                'ATR%': f"{params.atr_pct:.2f}%",
                '20日穿越': params.cross_count,
                'ADX': f"{params.adx:.1f}",
                '偏离度': f"{params.ma20_deviation:.2f}%",
                '箱体位置': params.in_box_position,
                '建议仓位': f"¥{params.total_allocation:.0f}"
            })
        
        summary_df = pd.DataFrame(summary_data)
        st.dataframe(summary_df, use_container_width=True)
        
        # 详细分析每个ETF
        st.markdown('<h2 class="sub-header">🔍 详细分析</h2>', unsafe_allow_html=True)
        
        for idx, params in enumerate(grid_params_list):
            with st.expander(f"第{idx+1}名: {params.symbol} - {params.name} (得分: {params.score:.1f})", expanded=idx==0):
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.markdown("### 📊 技术指标")
                    st.metric("ATR%", f"{params.atr_pct:.2f}%")
                    st.metric("20日穿越次数", params.cross_count)
                    st.metric("ADX指标", f"{params.adx:.1f}")
                    st.metric("平均偏离度", f"{params.ma20_deviation:.2f}%")
                
                with col2:
                    st.markdown("### 🎯 箱体分析")
                    st.metric("当前价格", f"¥{params.current_price:.3f}")
                    st.metric("箱体上轨", f"¥{params.upper_bound:.3f}")
                    st.metric("箱体下轨", f"¥{params.lower_bound:.3f}")
                    st.metric("箱体高度", f"{params.box_height_pct:.2f}%")
                    st.metric("箱体位置", params.in_box_position)
                
                with col3:
                    st.markdown("### ⚙️ 网格参数")
                    st.metric("网格间距", f"{params.grid_spacing_pct:.2f}%")
                    st.metric("网格层数", f"{params.grid_layers}层")
                    st.metric("总分配资金", f"¥{params.total_allocation:.0f}")
                    st.metric("每层金额", f"¥{params.grid_amount_per_layer:.0f}")
                    st.metric("初始仓位", f"¥{params.initial_position_amount:.0f}")
                
                # 获取详细数据
                df = system.fetch_etf_data(params.symbol, days=90)
                if df is not None:
                    # 价格图表
                    st.markdown("### 📈 价格走势与网格布局")
                    price_chart = system.create_price_chart(params.symbol, df, params)
                    st.plotly_chart(price_chart, use_container_width=True)
                    
                    # 技术指标图表
                    st.markdown("### 📊 技术指标分析")
                    tech_chart = system.create_technical_chart(df)
                    st.plotly_chart(tech_chart, use_container_width=True)
                    
                    # 操作建议
                    st.markdown("### 💡 操作建议")
                    
                    if params.in_box_position == 'upper':
                        st.warning("""
                        **当前在箱体上部，建议操作：**
                        1. 等待回调至箱体中部再建立初始仓位
                        2. 可先设置1-2层卖出网格
                        3. 耐心等待更好的买入时机
                        """)
                    elif params.in_box_position == 'middle':
                        st.success("""
                        **当前在箱体中部，建议操作：**
                        1. 立即建立30%初始仓位
                        2. 向上设置3-4层卖出网格
                        3. 向下设置2-3层买入网格
                        4. 预留资金应对突破
                        """)
                    else:  # lower
                        st.info("""
                        **当前在箱体下部，建议操作：**
                        1. 立即建立40-50%初始仓位
                        2. 主要向上设置卖出网格
                        3. 少量向下设置买入网格（防止破位）
                        4. 设置严格止损
                        """)
                    
                    # 风险提示
                    risk_notes = []
                    if params.score < 70:
                        risk_notes.append(f"综合得分较低 ({params.score:.1f})，建议谨慎操作")
                    if params.atr_pct < 2.0:
                        risk_notes.append(f"波动率较低 (ATR%={params.atr_pct:.2f}%)，网格利润空间有限")
                    if params.cross_count < 3:
                        risk_notes.append(f"震荡频率低 (20日穿越{params.cross_count}次)，可能趋势性强")
                    if params.adx > 30:
                        risk_notes.append(f"ADX指标较高 ({params.adx:.1f})，存在趋势性风险")
                    
                    if risk_notes:
                        st.markdown("### 🚨 风险提示")
                        for note in risk_notes:
                            st.warning(note)
                
                st.markdown("---")
        
        # 导出功能
        st.markdown('<h2 class="sub-header">💾 导出结果</h2>', unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        
        with col1:
            # 导出JSON
            if st.button("📥 导出JSON文件"):
                export_data = []
                for params in grid_params_list:
                    export_data.append(asdict(params))
                
                import json
                json_str = json.dumps(export_data, ensure_ascii=False, indent=2)
                
                st.download_button(
                    label="下载JSON文件",
                    data=json_str,
                    file_name=f"grid_strategy_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json"
                )
        
        with col2:
            # 导出CSV
            if st.button("📊 导出CSV文件"):
                csv_data = []
                for params in grid_params_list:
                    row = asdict(params)
                    csv_data.append(row)
                
                df_export = pd.DataFrame(csv_data)
                csv_str = df_export.to_csv(index=False, encoding='utf-8-sig')
                
                st.download_button(
                    label="下载CSV文件",
                    data=csv_str,
                    file_name=f"grid_strategy_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
        
        # 重置按钮
        if st.button("🔄 重新筛选"):
            st.session_state['run_screening'] = False
            st.rerun()
    
    else:
        # 首页说明
        st.markdown("""
        ## 🎯 系统介绍
        
        本系统专门为A股网格交易策略设计，通过量化指标自动筛选最适合网格交易的ETF，并动态计算最优网格参数。
        
        ### 📈 核心功能
        
        1. **智能筛选** - 基于多个技术指标自动筛选适合网格交易的ETF
        2. **动态参数** - 根据波动率动态计算网格间距和仓位
        3. **技术分析** - 包含ADX、ATR、均线偏离度等专业指标
        4. **可视化** - 交互式图表展示价格走势和网格布局
        5. **风险控制** - 自动识别风险并提供操作建议
        
        ### 🔧 使用步骤
        
        1. 在左侧边栏配置参数（资金量、筛选数量等）
        2. 选择要分析的ETF观察池
        3. 点击"开始筛选"按钮
        4. 查看筛选结果和详细分析
        5. 导出结果用于实际交易
        
        ### 📊 筛选指标
        
        | 指标 | 说明 | 权重 |
        |------|------|------|
        | ATR% | 波动率指标，越高越好 | 20% |
        | 20日穿越次数 | 震荡频率指标，越高越好 | 25% |
        | 平均偏离度 | 价格与20日均线的偏离度，越低越好 | 15% |
        | ADX | 趋势强度指标，越低越好 | 20% |
        | 流动性 | 成交额指标，越高越好 | 10% |
        | 箱体质量 | 价格在箱体内的稳定性，越高越好 | 10% |
        
        ### ⚠️ 注意事项
        
        1. 数据来源于公开接口，可能存在延迟
        2. 建议在实际交易前进行模拟测试
        3. 网格交易适合震荡市，单边市风险较大
        4. 请根据自身风险承受能力调整参数
        
        ### 🚀 开始使用
        
        请在左侧边栏配置参数，然后点击"开始筛选"按钮。
        """)
        
        # 显示系统状态
        st.info("💡 **系统状态**: 等待参数配置...")
        
        # 添加示例结果预览
        with st.expander("📋 查看示例输出"):
            st.image("https://via.placeholder.com/800x400.png?text=网格策略筛选结果示例", 
                    caption="示例输出界面")

if __name__ == "__main__":
    create_streamlit_app()