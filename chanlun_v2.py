import numpy as np
import pandas as pd
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass
from enum import Enum
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib import rcParams
from datetime import datetime, timedelta

# 设置中文字体
rcParams['font.sans-serif'] = ['SimHei', 'Arial Unicode MS', 'DejaVu Sans']
rcParams['axes.unicode_minus'] = False


class Direction(Enum):
    """方向枚举"""
    UP = 1  # 向上
    DOWN = -1  # 向下


class BuySellType(Enum):
    """买卖点类型枚举"""
    BUY1 = "第一类买点"  # 趋势背驰买点
    BUY2 = "第二类买点"  # 下跌不创新低买点
    BUY3 = "第三类买点"  # 突破后回踩不进入中枢买点
    SELL1 = "第一类卖点"  # 趋势背驰卖点
    SELL2 = "第二类卖点"  # 上涨不创新高卖点
    SELL3 = "第三类卖点"  # 跌破后反弹不进入中枢卖点


@dataclass
class KLine:
    """K线数据结构"""
    date: str  # 日期
    high: float  # 最高价
    low: float  # 最低价
    open: float  # 开盘价
    close: float  # 收盘价
    volume: float  # 成交量

    def __post_init__(self):
        self.merged = False  # 是否被合并
        self.index = None  # 在序列中的索引


@dataclass
class Fractal:
    """分型数据结构"""
    index: int  # K线索引
    price: float  # 分型价格
    type: Direction  # 分型类型(顶/底)
    kline: KLine  # 对应的K线

    def __str__(self):
        return f"{self.type.name}分型(位置:{self.index}, 价格:{self.price:.2f})"


@dataclass
class Bi:
    """笔数据结构"""
    start_fractal: Fractal  # 起点分型
    end_fractal: Fractal  # 终点分型
    direction: Direction  # 笔方向
    high: float  # 笔最高价
    low: float  # 笔最低价
    index: int = None  # 笔的序号

    def __str__(self):
        return f"笔{self.index}[{self.direction.name}]({self.start_fractal.index}->{self.end_fractal.index})"

    @property
    def length(self):
        """笔的长度(bar数)"""
        return abs(self.end_fractal.index - self.start_fractal.index)

    @property
    def price_change(self):
        """价格变动"""
        if self.direction == Direction.UP:
            return self.end_fractal.price - self.start_fractal.price
        else:
            return self.start_fractal.price - self.end_fractal.price

    @property
    def price_change_pct(self):
        """价格变动百分比"""
        if self.direction == Direction.UP:
            return (self.end_fractal.price - self.start_fractal.price) / self.start_fractal.price * 100
        else:
            return (self.start_fractal.price - self.end_fractal.price) / self.start_fractal.price * 100


@dataclass
class Segment:
    """线段数据结构"""
    start_bi: Bi  # 起始笔
    end_bi: Bi  # 结束笔
    direction: Direction  # 线段方向
    bis: List[Bi]  # 包含的笔序列
    index: int = None  # 线段序号

    def __str__(self):
        return f"线段{self.index}[{self.direction.name}]({self.start_bi.start_fractal.index}->{self.end_bi.end_fractal.index}, 笔数:{len(self.bis)})"

    @property
    def high(self):
        """线段最高价"""
        return max(bi.high for bi in self.bis)

    @property
    def low(self):
        """线段最低价"""
        return min(bi.low for bi in self.bis)


@dataclass
class ZhongShu:
    """中枢数据结构"""
    start_index: int  # 起始位置
    end_index: int  # 结束位置
    zg: float  # 中枢高点(最高最低的较低者)
    zd: float  # 中枢低点(最低最高的较高者)
    gg: float  # 所有高点最高值
    dd: float  # 所有低点最低值
    bis: List[Bi]  # 构成中枢的笔
    index: int = None  # 中枢序号

    def __str__(self):
        return f"中枢{self.index}[{self.start_index}-{self.end_index}](ZG:{self.zg:.2f}, ZD:{self.zd:.2f})"

    @property
    def range(self):
        """中枢价格区间"""
        return (self.zd, self.zg)

    @property
    def center(self):
        """中枢中轴"""
        return (self.zg + self.zd) / 2

    @property
    def width_pct(self):
        """中枢宽度百分比"""
        return (self.zg - self.zd) / self.zd * 100


@dataclass
class BuySellPoint:
    """买卖点数据结构"""
    type: BuySellType  # 买卖点类型
    index: int  # 位置索引
    price: float  # 价格
    confidence: float  # 置信度(0-1)
    reason: str  # 形成原因
    related_bi: Bi = None  # 相关笔
    related_zs: ZhongShu = None  # 相关中枢
    divergence: Dict = None  # 背驰信息

    def __str__(self):
        return f"{self.type.value}(位置:{self.index}, 价格:{self.price:.2f}, 置信度:{self.confidence:.2f})"


class ChanLunAnalyzer:
    """缠论分析器（增强版）"""

    def __init__(self, config=None):
        self.klines: List[KLine] = []
        self.merged_klines: List[KLine] = []
        self.fractals: List[Fractal] = []
        self.bis: List[Bi] = []
        self.segments: List[Segment] = []
        self.zhongshus: List[ZhongShu] = []
        self.buy_sell_points: List[BuySellPoint] = []

        # 配置参数
        self.config = config or {
            'min_bi_length': 4,  # 笔的最小长度(K线数)
            'min_zs_bi_count': 3,  # 中枢最小笔数
            'divergence_lookback': 20,  # 背驰回溯周期
            'macd_fast': 12,
            'macd_slow': 26,
            'macd_signal': 9
        }

    def add_kline(self, date, high, low, open, close, volume):
        """添加K线数据"""
        kline = KLine(date, high, low, open, close, volume)
        kline.index = len(self.klines)
        self.klines.append(kline)

    def add_klines_from_dataframe(self, df,
                                  date_col='date',
                                  high_col='high',
                                  low_col='low',
                                  open_col='open',
                                  close_col='close',
                                  volume_col='volume'):
        """从DataFrame添加K线数据"""
        for _, row in df.iterrows():
            self.add_kline(
                str(row[date_col]),
                float(row[high_col]),
                float(row[low_col]),
                float(row[open_col]),
                float(row[close_col]),
                float(row[volume_col])
            )

    def process_containing_relationship(self):
        """处理K线包含关系"""
        if len(self.klines) < 2:
            return

        merged = []
        i = 0

        while i < len(self.klines):
            if i == len(self.klines) - 1:
                # 最后一根K线，直接加入
                self.klines[i].index = len(merged)
                merged.append(self.klines[i])
                break

            current = self.klines[i]
            next_k = self.klines[i + 1]

            # 判断是否有包含关系
            if self._has_containing_relationship(current, next_k):
                # 处理包含关系
                merged_k = self._merge_klines(current, next_k)
                merged_k.index = len(merged)
                merged.append(merged_k)

                # 继续检查后续K线是否还与合并后的K线存在包含关系
                j = i + 2
                while j < len(self.klines):
                    if self._has_containing_relationship(merged_k, self.klines[j]):
                        merged_k = self._merge_klines(merged_k, self.klines[j])
                        merged_k.index = len(merged) - 1
                        merged[-1] = merged_k
                        j += 1
                    else:
                        break
                i = j
            else:
                # 没有包含关系，直接加入
                current.index = len(merged)
                merged.append(current)
                i += 1

        self.merged_klines = merged
        return merged

    def _has_containing_relationship(self, k1: KLine, k2: KLine) -> bool:
        """判断两根K线是否有包含关系"""
        up_contain = k2.high <= k1.high and k2.low >= k1.low
        down_contain = k2.high >= k1.high and k2.low <= k1.low

        return up_contain or down_contain

    def _merge_klines(self, k1: KLine, k2: KLine) -> KLine:
        """合并两根有包含关系的K线"""
        # 确定方向：如果k1是阳线，则按上升处理；如果是阴线，则按下降处理
        direction_up = k1.close >= k1.open

        if direction_up:
            # 上升趋势合并，取高点的高点和低点的高点
            high = max(k1.high, k2.high)
            low = max(k1.low, k2.low)
        else:
            # 下降趋势合并，取高点的低点和低点的低点
            high = min(k1.high, k2.high)
            low = min(k1.low, k2.low)

        # 使用第一根K线的开盘、收盘、成交量
        return KLine(
            date=k1.date,
            high=high,
            low=low,
            open=k1.open,
            close=k1.close,
            volume=k1.volume + k2.volume
        )

    def find_fractals(self):
        """寻找分型"""
        if len(self.merged_klines) < 5:
            return []

        fractals = []

        for i in range(2, len(self.merged_klines) - 2):
            klines_slice = self.merged_klines[i - 2:i + 3]

            # 检查是否满足顶分型条件
            if self._is_top_fractal(klines_slice):
                fractals.append(Fractal(
                    index=i,
                    price=self.merged_klines[i].high,
                    type=Direction.DOWN,
                    kline=self.merged_klines[i]
                ))

            # 检查是否满足底分型条件
            elif self._is_bottom_fractal(klines_slice):
                fractals.append(Fractal(
                    index=i,
                    price=self.merged_klines[i].low,
                    type=Direction.UP,
                    kline=self.merged_klines[i]
                ))

        # 过滤掉相邻的同向分型（取最极值的那个）
        filtered_fractals = []
        i = 0
        while i < len(fractals):
            current = fractals[i]

            if i == len(fractals) - 1:
                filtered_fractals.append(current)
                break

            next_f = fractals[i + 1]

            if current.type == next_f.type:
                # 同向分型，取更极值的那个
                if current.type == Direction.DOWN:  # 顶分型，取更高的
                    if current.price >= next_f.price:
                        filtered_fractals.append(current)
                    else:
                        filtered_fractals.append(next_f)
                else:  # 底分型，取更低的
                    if current.price <= next_f.price:
                        filtered_fractals.append(current)
                    else:
                        filtered_fractals.append(next_f)
                i += 2
            else:
                filtered_fractals.append(current)
                i += 1

        self.fractals = filtered_fractals
        return filtered_fractals

    def _is_top_fractal(self, klines: List[KLine]) -> bool:
        """判断是否是顶分型"""
        if len(klines) != 5:
            return False

        center = klines[2]
        left1, left2 = klines[1], klines[0]
        right1, right2 = klines[3], klines[4]

        # 条件1：中间K线高点最高
        if not (center.high >= left1.high and center.high >= left2.high and
                center.high >= right1.high and center.high >= right2.high):
            return False

        # 条件2：中间K线低点也高于左右相邻K线的低点
        if not (center.low >= left1.low and center.low >= right1.low):
            return False

        return True

    def _is_bottom_fractal(self, klines: List[KLine]) -> bool:
        """判断是否是底分型"""
        if len(klines) != 5:
            return False

        center = klines[2]
        left1, left2 = klines[1], klines[0]
        right1, right2 = klines[3], klines[4]

        # 条件1：中间K线低点最低
        if not (center.low <= left1.low and center.low <= left2.low and
                center.low <= right1.low and center.low <= right2.low):
            return False

        # 条件2：中间K线高点也低于左右相邻K线的高点
        if not (center.high <= left1.high and center.high <= right1.high):
            return False

        return True

    def find_bis(self):
        """划分笔"""
        if len(self.fractals) < 2:
            return []

        bis = []
        i = 0

        while i < len(self.fractals) - 1:
            start_fractal = self.fractals[i]

            # 寻找下一个反向分型作为笔的终点
            j = i + 1
            while j < len(self.fractals):
                end_fractal = self.fractals[j]

                # 检查方向是否相反
                if start_fractal.type != end_fractal.type:
                    # 检查是否满足笔的条件：至少5根K线
                    kline_count = end_fractal.index - start_fractal.index

                    if kline_count >= self.config['min_bi_length'] - 1:
                        # 确定笔的方向
                        if start_fractal.type == Direction.UP:  # 底分型开始，向上笔
                            direction = Direction.UP
                            high = max(k.high for k in self.merged_klines[start_fractal.index:end_fractal.index + 1])
                            low = min(k.low for k in self.merged_klines[start_fractal.index:end_fractal.index + 1])
                        else:  # 顶分型开始，向下笔
                            direction = Direction.DOWN
                            high = max(k.high for k in self.merged_klines[start_fractal.index:end_fractal.index + 1])
                            low = min(k.low for k in self.merged_klines[start_fractal.index:end_fractal.index + 1])

                        bi = Bi(
                            start_fractal=start_fractal,
                            end_fractal=end_fractal,
                            direction=direction,
                            high=high,
                            low=low,
                            index=len(bis) + 1
                        )
                        bis.append(bi)
                        i = j  # 从当前终点开始寻找下一笔
                        break

                j += 1

            if j >= len(self.fractals):
                break

        self.bis = bis
        return bis

    def find_segments(self):
        """划分线段（简化版）"""
        if len(self.bis) < 3:
            return []

        segments = []
        i = 0

        while i < len(self.bis) - 2:
            start_bi = self.bis[i]

            # 检查是否满足线段破坏的条件
            j = i + 2
            while j < len(self.bis):
                current_bis = self.bis[i:j + 1]

                if self._is_segment_destroyed(current_bis):
                    segment_bis = self.bis[i:j + 1]

                    # 确定线段方向（第一笔的方向）
                    direction = segment_bis[0].direction

                    segment = Segment(
                        start_bi=segment_bis[0],
                        end_bi=segment_bis[-1],
                        direction=direction,
                        bis=segment_bis.copy(),
                        index=len(segments) + 1
                    )
                    segments.append(segment)
                    i = j + 1
                    break

                j += 1

            if j >= len(self.bis):
                break

        self.segments = segments
        return segments

    def _is_segment_destroyed(self, bis: List[Bi]) -> bool:
        """判断线段是否被破坏（简化版）"""
        if len(bis) < 3:
            return False

        if bis[0].direction == Direction.DOWN:  # 向下线段
            return (bis[1].low < bis[0].low and bis[1].low < bis[2].low)
        else:  # 向上线段
            return (bis[1].high > bis[0].high and bis[1].high > bis[2].high)

    def find_zhongshus(self):
        """寻找中枢"""
        if len(self.bis) < self.config['min_zs_bi_count']:
            return []

        zhongshus = []

        for i in range(len(self.bis) - self.config['min_zs_bi_count'] + 1):
            for j in range(i + self.config['min_zs_bi_count'] - 1, len(self.bis)):
                candidate_bis = self.bis[i:j + 1]

                if self._is_zhongshu(candidate_bis):
                    highs = [bi.high for bi in candidate_bis]
                    lows = [bi.low for bi in candidate_bis]

                    gg = max(highs)
                    dd = min(lows)

                    overlap_highs = []
                    overlap_lows = []

                    for k in range(len(candidate_bis) - 1):
                        bi1 = candidate_bis[k]
                        bi2 = candidate_bis[k + 1]

                        # 检查两笔是否有重叠
                        if bi1.high >= bi2.low and bi2.high >= bi1.low:
                            overlap_high = min(bi1.high, bi2.high)
                            overlap_low = max(bi1.low, bi2.low)
                            overlap_highs.append(overlap_high)
                            overlap_lows.append(overlap_low)

                    if overlap_highs and overlap_lows:
                        zg = min(overlap_highs)
                        zd = max(overlap_lows)

                        # 中枢必须满足ZG > ZD
                        if zg > zd:
                            zhongshu = ZhongShu(
                                start_index=candidate_bis[0].start_fractal.index,
                                end_index=candidate_bis[-1].end_fractal.index,
                                zg=zg,
                                zd=zd,
                                gg=gg,
                                dd=dd,
                                bis=candidate_bis.copy(),
                                index=len(zhongshus) + 1
                            )
                            zhongshus.append(zhongshu)

        # 过滤重叠的中枢
        filtered_zhongshus = []
        i = 0
        while i < len(zhongshus):
            current = zhongshus[i]
            filtered_zhongshus.append(current)

            j = i + 1
            while j < len(zhongshus):
                next_zs = zhongshus[j]
                if not (current.end_index < next_zs.start_index or
                        next_zs.end_index < current.start_index):
                    j += 1
                else:
                    break
            i = j

        self.zhongshus = filtered_zhongshus
        return filtered_zhongshus

    def _is_zhongshu(self, bis: List[Bi]) -> bool:
        """判断一组笔是否构成中枢"""
        if len(bis) < self.config['min_zs_bi_count']:
            return False

        # 检查笔的方向是否交替
        for i in range(len(bis) - 1):
            if bis[i].direction == bis[i + 1].direction:
                return False

        # 检查是否有足够的重叠
        overlap_count = 0
        for i in range(len(bis) - 1):
            bi1 = bis[i]
            bi2 = bis[i + 1]

            if bi1.high >= bi2.low and bi2.high >= bi1.low:
                overlap_count += 1

        return overlap_count >= 2

    def detect_divergence(self):
        """检测MACD背驰"""
        if len(self.klines) < self.config['macd_slow']:
            return []

        closes = [k.close for k in self.klines]
        df = pd.DataFrame({'close': closes})

        df['ema_fast'] = df['close'].ewm(span=self.config['macd_fast'], adjust=False).mean()
        df['ema_slow'] = df['close'].ewm(span=self.config['macd_slow'], adjust=False).mean()
        df['diff'] = df['ema_fast'] - df['ema_slow']
        df['dea'] = df['diff'].ewm(span=self.config['macd_signal'], adjust=False).mean()
        df['macd'] = (df['diff'] - df['dea']) * 2

        divergences = []

        # 检测顶背驰和底背驰
        for i in range(len(self.bis) - 1):
            current_bi = self.bis[i]
            next_bi = self.bis[i + 1]

            # 检查是否是同向笔
            if current_bi.direction == next_bi.direction == Direction.UP:
                # 价格创新高，但MACD未创新高（顶背驰）
                price_higher = next_bi.high > current_bi.high

                current_macd = df['macd'].iloc[current_bi.end_fractal.index]
                next_macd = df['macd'].iloc[next_bi.end_fractal.index]

                macd_lower = next_macd < current_macd

                if price_higher and macd_lower:
                    divergences.append({
                        'type': '顶背驰',
                        'position': f"笔{current_bi.index}->笔{next_bi.index}",
                        'price_change': f"{current_bi.high:.2f}->{next_bi.high:.2f}",
                        'macd_change': f"{current_macd:.4f}->{next_macd:.4f}",
                        'current_bi': current_bi,
                        'next_bi': next_bi
                    })

            elif current_bi.direction == next_bi.direction == Direction.DOWN:
                # 价格创新低，但MACD未创新低（底背驰）
                price_lower = next_bi.low < current_bi.low

                current_macd = df['macd'].iloc[current_bi.end_fractal.index]
                next_macd = df['macd'].iloc[next_bi.end_fractal.index]

                macd_higher = next_macd > current_macd

                if price_lower and macd_higher:
                    divergences.append({
                        'type': '底背驰',
                        'position': f"笔{current_bi.index}->笔{next_bi.index}",
                        'price_change': f"{current_bi.low:.2f}->{next_bi.low:.2f}",
                        'macd_change': f"{current_macd:.4f}->{next_macd:.4f}",
                        'current_bi': current_bi,
                        'next_bi': next_bi
                    })

        return divergences

    def find_buy_sell_points(self):
        """识别买卖点"""
        if len(self.bis) < 5 or len(self.zhongshus) < 1:
            return []

        buy_sell_points = []
        divergences = self.detect_divergence()

        # 1. 第一类买卖点（趋势背驰）
        for div in divergences:
            if div['type'] == '底背驰':
                # 第一类买点：下跌趋势中的底背驰
                point = BuySellPoint(
                    type=BuySellType.BUY1,
                    index=div['next_bi'].end_fractal.index,
                    price=div['next_bi'].end_fractal.price,
                    confidence=0.8,
                    reason=f"下跌趋势背驰，MACD不创新低",
                    related_bi=div['next_bi'],
                    divergence=div
                )
                buy_sell_points.append(point)

            elif div['type'] == '顶背驰':
                # 第一类卖点：上涨趋势中的顶背驰
                point = BuySellPoint(
                    type=BuySellType.SELL1,
                    index=div['next_bi'].end_fractal.index,
                    price=div['next_bi'].end_fractal.price,
                    confidence=0.8,
                    reason=f"上涨趋势背驰，MACD不创新高",
                    related_bi=div['next_bi'],
                    divergence=div
                )
                buy_sell_points.append(point)

        # 2. 第二类买卖点
        for i in range(1, len(self.bis) - 1):
            prev_bi = self.bis[i - 1]
            current_bi = self.bis[i]
            next_bi = self.bis[i + 1]

            if (prev_bi.direction == Direction.DOWN and
                    current_bi.direction == Direction.UP and
                    next_bi.direction == Direction.DOWN):
                # 下跌-上涨-下跌结构，检查是否形成第二类买点
                if next_bi.low > current_bi.low:  # 不创新低
                    # 查找附近的中枢
                    nearby_zs = self._find_nearby_zhongshu(current_bi.end_fractal.index)

                    point = BuySellPoint(
                        type=BuySellType.BUY2,
                        index=next_bi.end_fractal.index,
                        price=next_bi.end_fractal.price,
                        confidence=0.7,
                        reason=f"下跌后反弹再下跌不创新低",
                        related_bi=next_bi,
                        related_zs=nearby_zs[0] if nearby_zs else None
                    )
                    buy_sell_points.append(point)

            elif (prev_bi.direction == Direction.UP and
                  current_bi.direction == Direction.DOWN and
                  next_bi.direction == Direction.UP):
                # 上涨-下跌-上涨结构，检查是否形成第二类卖点
                if next_bi.high < current_bi.high:  # 不创新高
                    nearby_zs = self._find_nearby_zhongshu(current_bi.end_fractal.index)

                    point = BuySellPoint(
                        type=BuySellType.SELL2,
                        index=next_bi.end_fractal.index,
                        price=next_bi.end_fractal.price,
                        confidence=0.7,
                        reason=f"上涨后回调再上涨不创新高",
                        related_bi=next_bi,
                        related_zs=nearby_zs[0] if nearby_zs else None
                    )
                    buy_sell_points.append(point)

        # 3. 第三类买卖点
        for zs in self.zhongshus:
            # 查找中枢后的笔
            for i in range(len(self.bis)):
                bi = self.bis[i]
                if bi.start_fractal.index > zs.end_index:
                    # 检查是否形成第三类买点（向上突破后回踩不进入中枢）
                    if (bi.direction == Direction.DOWN and
                            bi.low > zs.zg and  # 回踩不进入中枢
                            i > 0 and self.bis[i - 1].direction == Direction.UP and
                            self.bis[i - 1].high > zs.gg):  # 前一笔向上突破中枢

                        point = BuySellPoint(
                            type=BuySellType.BUY3,
                            index=bi.end_fractal.index,
                            price=bi.end_fractal.price,
                            confidence=0.75,
                            reason=f"突破中枢后回踩不进入中枢",
                            related_bi=bi,
                            related_zs=zs
                        )
                        buy_sell_points.append(point)

                    # 检查是否形成第三类卖点（向下突破后反弹不进入中枢）
                    elif (bi.direction == Direction.UP and
                          bi.high < zs.zd and  # 反弹不进入中枢
                          i > 0 and self.bis[i - 1].direction == Direction.DOWN and
                          self.bis[i - 1].low < zs.dd):  # 前一笔向下突破中枢

                        point = BuySellPoint(
                            type=BuySellType.SELL3,
                            index=bi.end_fractal.index,
                            price=bi.end_fractal.price,
                            confidence=0.75,
                            reason=f"跌破中枢后反弹不进入中枢",
                            related_bi=bi,
                            related_zs=zs
                        )
                        buy_sell_points.append(point)

        # 按时间排序并过滤重复点
        buy_sell_points.sort(key=lambda x: x.index)
        filtered_points = []
        for point in buy_sell_points:
            if not filtered_points or point.index - filtered_points[-1].index > 5:
                filtered_points.append(point)

        self.buy_sell_points = filtered_points
        return filtered_points

    def _find_nearby_zhongshu(self, index: int, window: int = 20) -> List[ZhongShu]:
        """查找附近的中心"""
        nearby = []
        for zs in self.zhongshus:
            if abs(zs.center - index) < window:
                nearby.append(zs)
        return nearby

    def analyze(self):
        """执行完整分析"""
        print("开始缠论分析...")
        print(f"原始K线数量: {len(self.klines)}")

        # 处理包含关系
        self.process_containing_relationship()
        print(f"合并后K线数量: {len(self.merged_klines)}")

        # 寻找分型
        fractals = self.find_fractals()
        print(f"找到分型数量: {len(fractals)}")

        # 划分笔
        bis = self.find_bis()
        print(f"划分笔数量: {len(bis)}")

        # 寻找中枢
        zhongshus = self.find_zhongshus()
        print(f"找到中枢数量: {len(zhongshus)}")

        # 检测背驰
        divergences = self.detect_divergence()
        print(f"检测到背驰数量: {len(divergences)}")

        # 识别买卖点
        buy_sell_points = self.find_buy_sell_points()
        print(f"识别买卖点数量: {len(buy_sell_points)}")

        # 输出买卖点详情
        print("\n买卖点详情:")
        for point in buy_sell_points:
            print(f"  {point}")
            print(f"    原因: {point.reason}")

        return {
            'fractals': fractals,
            'bis': bis,
            'zhongshus': zhongshus,
            'divergences': divergences,
            'buy_sell_points': buy_sell_points
        }

    def plot_analysis(self, start_idx=0, end_idx=None, show_buy_sell=True):
        """可视化分析结果"""
        if end_idx is None:
            end_idx = len(self.klines)

        # 准备数据
        dates = [k.date for k in self.klines[start_idx:end_idx]]
        highs = [k.high for k in self.klines[start_idx:end_idx]]
        lows = [k.low for k in self.klines[start_idx:end_idx]]
        opens = [k.open for k in self.klines[start_idx:end_idx]]
        closes = [k.close for k in self.klines[start_idx:end_idx]]

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(18, 12),
                                       gridspec_kw={'height_ratios': [3, 1]})

        # 绘制K线
        for i in range(len(dates)):
            color = 'red' if closes[i] >= opens[i] else 'green'
            ax1.plot([i, i], [lows[i], highs[i]], color=color, linewidth=1)
            ax1.plot([i, i], [opens[i], closes[i]], color=color, linewidth=3)

        # 绘制分型
        top_fractals = [f for f in self.fractals if f.type == Direction.DOWN
                        and start_idx <= f.index <= end_idx]
        bottom_fractals = [f for f in self.fractals if f.type == Direction.UP
                           and start_idx <= f.index <= end_idx]

        top_x = [f.index - start_idx for f in top_fractals]
        top_y = [f.price for f in top_fractals]
        ax1.scatter(top_x, top_y, color='red', s=100, marker='v',
                    label='顶分型', zorder=5)

        bottom_x = [f.index - start_idx for f in bottom_fractals]
        bottom_y = [f.price for f in bottom_fractals]
        ax1.scatter(bottom_x, bottom_y, color='green', s=100, marker='^',
                    label='底分型', zorder=5)

        # 绘制笔
        for bi in self.bis:
            start_idx_bi = bi.start_fractal.index
            end_idx_bi = bi.end_fractal.index

            if start_idx <= start_idx_bi <= end_idx and start_idx <= end_idx_bi <= end_idx:
                x_start = start_idx_bi - start_idx
                x_end = end_idx_bi - start_idx
                y_start = bi.start_fractal.price
                y_end = bi.end_fractal.price

                color = 'red' if bi.direction == Direction.UP else 'blue'
                ax1.plot([x_start, x_end], [y_start, y_end],
                         color=color, linewidth=2, alpha=0.7,
                         label='笔' if bi == self.bis[0] else "")

                # 标注笔序号
                mid_x = (x_start + x_end) / 2
                mid_y = (y_start + y_end) / 2
                ax1.text(mid_x, mid_y, f'B{bi.index}', fontsize=8,
                         bbox=dict(boxstyle="round,pad=0.2", facecolor="white", alpha=0.7))

        # 绘制中枢
        for zs in self.zhongshus:
            if start_idx <= zs.start_index <= end_idx or start_idx <= zs.end_index <= end_idx:
                x_start = max(zs.start_index, start_idx) - start_idx
                x_end = min(zs.end_index, end_idx) - start_idx

                # 绘制中枢区间
                rect = patches.Rectangle(
                    (x_start, zs.zd),
                    x_end - x_start,
                    zs.zg - zs.zd,
                    linewidth=2,
                    edgecolor='purple',
                    facecolor='yellow',
                    alpha=0.3
                )
                ax1.add_patch(rect)

                # 标注中枢
                ax1.text((x_start + x_end) / 2, (zs.zg + zs.zd) / 2,
                         f'ZS{zs.index}\nZG:{zs.zg:.2f}\nZD:{zs.zd:.2f}',
                         ha='center', va='center', fontsize=8,
                         bbox=dict(boxstyle="round,pad=0.3", facecolor="yellow", alpha=0.7))

        # 绘制买卖点
        if show_buy_sell:
            buy_colors = {
                BuySellType.BUY1: 'darkgreen',
                BuySellType.BUY2: 'limegreen',
                BuySellType.BUY3: 'lightgreen'
            }

            sell_colors = {
                BuySellType.SELL1: 'darkred',
                BuySellType.SELL2: 'red',
                BuySellType.SELL3: 'lightcoral'
            }

            markers = {
                BuySellType.BUY1: '^',
                BuySellType.BUY2: '^',
                BuySellType.BUY3: '^',
                BuySellType.SELL1: 'v',
                BuySellType.SELL2: 'v',
                BuySellType.SELL3: 'v'
            }

            for point in self.buy_sell_points:
                if start_idx <= point.index <= end_idx:
                    x = point.index - start_idx
                    y = point.price

                    color_dict = buy_colors if 'BUY' in point.type.name else sell_colors
                    color = color_dict.get(point.type, 'black')
                    marker = markers.get(point.type, 'o')
                    size = 120 if '1' in point.type.value else 80

                    ax1.scatter(x, y, color=color, s=size, marker=marker,
                                zorder=10, edgecolors='black', linewidth=1.5)

                    # 标注买卖点类型
                    offset = -2 if 'BUY' in point.type.name else 2
                    ax1.text(x, y + offset, point.type.value, fontsize=9,
                             ha='center', va='center' if 'BUY' in point.type.name else 'center',
                             bbox=dict(boxstyle="round,pad=0.2", facecolor=color, alpha=0.8))

        ax1.set_title('缠论分析图 - 买卖点识别', fontsize=16, fontweight='bold')
        ax1.set_xlabel('K线序号')
        ax1.set_ylabel('价格')
        ax1.grid(True, alpha=0.3)
        ax1.legend(loc='upper left')

        # 设置X轴刻度
        step = max(1, len(dates) // 10)
        ax1.set_xticks(range(0, len(dates), step))
        ax1.set_xticklabels([dates[i] for i in range(0, len(dates), step)], rotation=45)

        # 绘制MACD
        closes = [k.close for k in self.klines]
        df = pd.DataFrame({'close': closes})
        df['ema12'] = df['close'].ewm(span=12, adjust=False).mean()
        df['ema26'] = df['close'].ewm(span=26, adjust=False).mean()
        df['diff'] = df['ema12'] - df['ema26']
        df['dea'] = df['diff'].ewm(span=9, adjust=False).mean()
        df['macd'] = (df['diff'] - df['dea']) * 2

        macd_values = df['macd'].iloc[start_idx:end_idx].values

        # 绘制MACD柱状图
        colors = ['red' if val >= 0 else 'green' for val in macd_values]
        ax2.bar(range(len(macd_values)), macd_values, color=colors, alpha=0.7)

        # 绘制DIFF和DEA线
        diff_values = df['diff'].iloc[start_idx:end_idx].values
        dea_values = df['dea'].iloc[start_idx:end_idx].values

        ax2.plot(range(len(diff_values)), diff_values, color='blue',
                 label='DIFF', linewidth=1.5)
        ax2.plot(range(len(dea_values)), dea_values, color='orange',
                 label='DEA', linewidth=1.5)

        ax2.axhline(y=0, color='black', linestyle='-', alpha=0.3)
        ax2.set_title('MACD指标', fontsize=12)
        ax2.set_xlabel('K线序号')
        ax2.set_ylabel('MACD')
        ax2.grid(True, alpha=0.3)
        ax2.legend(loc='upper left')

        # 设置X轴刻度
        ax2.set_xticks(range(0, len(dates), step))
        ax2.set_xticklabels([dates[i] for i in range(0, len(dates), step)], rotation=45)

        plt.tight_layout()
        plt.show()

    def generate_trading_signals(self):
        """生成交易信号"""
        if not self.buy_sell_points:
            return []

        signals = []
        for point in self.buy_sell_points:
            signal = {
                'date': self.klines[point.index].date if point.index < len(self.klines) else '未知',
                'type': point.type.value,
                'price': point.price,
                'confidence': point.confidence,
                'action': '买入' if 'BUY' in point.type.name else '卖出',
                'stop_loss': self._calculate_stop_loss(point),
                'take_profit': self._calculate_take_profit(point),
                'reason': point.reason
            }
            signals.append(signal)

        return signals

    def _calculate_stop_loss(self, point: BuySellPoint) -> float:
        """计算止损位"""
        if point.type in [BuySellType.BUY1, BuySellType.BUY2, BuySellType.BUY3]:
            # 买入点的止损设在最近的低点下方
            if point.related_bi:
                return point.related_bi.low * 0.98
            return point.price * 0.95
        else:
            # 卖出点的止损设在最近的高点上方
            if point.related_bi:
                return point.related_bi.high * 1.02
            return point.price * 1.05

    def _calculate_take_profit(self, point: BuySellPoint) -> float:
        """计算止盈位"""
        if point.type in [BuySellType.BUY1, BuySellType.BUY2, BuySellType.BUY3]:
            # 买入点的止盈设在最近的阻力位
            if point.related_zs:
                return point.related_zs.zg * 1.05
            return point.price * 1.10
        else:
            # 卖出点的止盈设在最近的支撑位
            if point.related_zs:
                return point.related_zs.zd * 0.95
            return point.price * 0.90

    def get_analysis_report(self):
        """生成分析报告"""
        report = []
        report.append("=" * 60)
        report.append("缠论分析报告")
        report.append("=" * 60)

        report.append(f"\n1. 市场结构分析:")
        report.append(f"   笔数量: {len(self.bis)}")
        report.append(f"   中枢数量: {len(self.zhongshus)}")
        report.append(f"   买卖点数量: {len(self.buy_sell_points)}")

        if self.bis:
            last_bi = self.bis[-1]
            report.append(f"\n2. 当前市场状态:")
            report.append(f"   当前笔方向: {last_bi.direction.name}")
            report.append(f"   当前笔幅度: {last_bi.price_change_pct:.2f}%")
            report.append(f"   当前笔长度: {last_bi.length}根K线")

        if self.zhongshus:
            last_zs = self.zhongshus[-1]
            report.append(f"\n3. 最近中枢:")
            report.append(f"   中枢区间: {last_zs.zd:.2f} - {last_zs.zg:.2f}")
            report.append(f"   中枢宽度: {last_zs.width_pct:.2f}%")
            report.append(f"   构成笔数: {len(last_zs.bis)}")

        if self.buy_sell_points:
            report.append(f"\n4. 近期买卖点:")
            for point in self.buy_sell_points[-3:]:  # 显示最近的3个
                report.append(f"   {point.type.value}: 价格{point.price:.2f}, 置信度{point.confidence:.2f}")
                report.append(f"     原因: {point.reason}")

        report.append(f"\n5. 交易建议:")
        if self.buy_sell_points:
            last_point = self.buy_sell_points[-1]
            if 'BUY' in last_point.type.name:
                report.append(f"   最近出现{last_point.type.value}，可考虑分批买入")
                report.append(f"   建议止损: {self._calculate_stop_loss(last_point):.2f}")
                report.append(f"   建议止盈: {self._calculate_take_profit(last_point):.2f}")
            else:
                report.append(f"   最近出现{last_point.type.value}，建议减仓或观望")
        else:
            report.append(f"   当前无明显买卖点，建议观望")

        report.append(f"\n6. 风险提示:")
        report.append(f"   本分析基于缠论技术分析，仅供参考")
        report.append(f"   实际交易需结合基本面、资金管理、风险控制")
        report.append(f"   市场有风险，投资需谨慎")

        return "\n".join(report)


# 使用示例
def generate_sample_data_with_trends(num_bars=200):
    """生成包含明显趋势的示例数据"""
    np.random.seed(42)

    dates = pd.date_range(start='2024-01-01', periods=num_bars, freq='D')
    base_price = 100

    prices = [base_price]
    trends = []

    # 生成明显的趋势段
    for i in range(1, num_bars):
        if i < 40:
            # 第一段下跌
            trend = -0.15
        elif i < 80:
            # 第一段上涨
            trend = 0.18
        elif i < 120:
            # 第二段下跌（背驰段）
            trend = -0.12
        elif i < 160:
            # 第二段上涨
            trend = 0.15
        else:
            # 最后震荡
            trend = 0.02

        noise = np.random.normal(0, 1)
        change = trend + noise * 0.3

        new_price = prices[-1] * (1 + change / 100)
        prices.append(new_price)
        trends.append(trend)

    # 生成OHLC数据
    data = []
    for i in range(num_bars):
        close = prices[i]
        open = close * (1 + np.random.normal(0, 0.3) / 100)
        high = max(open, close) * (1 + abs(np.random.normal(0, 0.5)) / 100)
        low = min(open, close) * (1 - abs(np.random.normal(0, 0.5)) / 100)
        volume = np.random.randint(10000, 100000) * (1 + abs(trends[i - 1] if i > 0 else 0) * 10)

        data.append({
            'date': dates[i].strftime('%Y-%m-%d'),
            'open': round(open, 2),
            'high': round(high, 2),
            'low': round(low, 2),
            'close': round(close, 2),
            'volume': volume
        })

    return pd.DataFrame(data)


def main():
    """主函数"""
    print("缠论分析系统 - 买卖点识别增强版")
    print("=" * 50)

    # 生成示例数据
    print("\n1. 生成示例数据...")
    df = generate_sample_data_with_trends(200)
    print(f"数据形状: {df.shape}")

    # 创建分析器
    analyzer = ChanLunAnalyzer()

    # 添加数据
    analyzer.add_klines_from_dataframe(df)

    # 执行分析
    print("\n2. 执行缠论分析...")
    results = analyzer.analyze()

    # 可视化结果
    print("\n3. 生成分析图表...")
    analyzer.plot_analysis(50, 180, show_buy_sell=True)

    # 生成交易信号
    print("\n4. 生成交易信号...")
    signals = analyzer.generate_trading_signals()
    if signals:
        print("最近交易信号:")
        for signal in signals[-3:]:  # 显示最近3个信号
            print(f"  日期: {signal['date']}, 类型: {signal['type']}")
            print(f"  价格: {signal['price']:.2f}, 操作: {signal['action']}")
            print(f"  止损: {signal['stop_loss']:.2f}, 止盈: {signal['take_profit']:.2f}")
            print(f"  理由: {signal['reason']}")
            print()

    # 输出完整分析报告
    print("\n5. 分析报告:")
    print(analyzer.get_analysis_report())

    # 保存分析结果
    print("\n6. 保存分析结果...")
    save_results = input("是否保存分析结果到文件? (y/n): ")
    if save_results.lower() == 'y':
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"chanlun_analysis_{timestamp}.txt"

        with open(filename, 'w', encoding='utf-8') as f:
            f.write(analyzer.get_analysis_report())
            f.write("\n\n详细买卖点:\n")
            for point in analyzer.buy_sell_points:
                f.write(f"{point}\n")
                f.write(f"  原因: {point.reason}\n")
                if point.related_bi:
                    f.write(f"  相关笔: {point.related_bi}\n")
                if point.related_zs:
                    f.write(f"  相关中枢: {point.related_zs}\n")
                f.write("\n")

        print(f"分析结果已保存到: {filename}")


if __name__ == "__main__":
    main()