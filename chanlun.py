import numpy as np
import pandas as pd
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib import rcParams

# 设置中文字体
rcParams['font.sans-serif'] = ['SimHei', 'Arial Unicode MS', 'DejaVu Sans']
rcParams['axes.unicode_minus'] = False


class Direction(Enum):
    """方向枚举"""
    UP = 1  # 向上
    DOWN = -1  # 向下


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

    def __str__(self):
        return f"笔[{self.direction.name}]({self.start_fractal.index}->{self.end_fractal.index})"

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


@dataclass
class Segment:
    """线段数据结构"""
    start_bi: Bi  # 起始笔
    end_bi: Bi  # 结束笔
    direction: Direction  # 线段方向
    bis: List[Bi]  # 包含的笔序列

    def __str__(self):
        return f"线段[{self.direction.name}]({self.start_bi.start_fractal.index}->{self.end_bi.end_fractal.index}, 笔数:{len(self.bis)})"

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

    def __str__(self):
        return f"中枢[{self.start_index}-{self.end_index}](ZG:{self.zg:.2f}, ZD:{self.zd:.2f})"

    @property
    def range(self):
        """中枢价格区间"""
        return (self.zd, self.zg)

    @property
    def center(self):
        """中枢中轴"""
        return (self.zg + self.zd) / 2


class ChanLunAnalyzer:
    """缠论分析器"""

    def __init__(self):
        self.klines: List[KLine] = []
        self.merged_klines: List[KLine] = []
        self.fractals: List[Fractal] = []
        self.bis: List[Bi] = []
        self.segments: List[Segment] = []
        self.zhongshus: List[ZhongShu] = []

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
        # 上升趋势包含：k2的高点<=k1的高点 且 k2的低点>=k1的低点
        # 下降趋势包含：k2的高点>=k1的高点 且 k2的低点<=k1的低点
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

        # 使用第一根K线的开盘、收盘、成交量（按缠论原文，这些不重要）
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

        # 中间K线是第3根
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

        # 条件3：排除包含关系的影响（在已处理包含关系后，此条件可简化）
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

                    if kline_count >= 4:  # 包含起点和终点，所以实际K线数≥5
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
                            low=low
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
            # 线段至少需要3笔
            start_bi = self.bis[i]

            # 检查是否满足线段破坏的条件
            j = i + 2
            while j < len(self.bis):
                # 简化处理：连续3笔有重叠部分即构成线段
                current_bis = self.bis[i:j + 1]

                # 检查这3笔是否构成特征序列分型（简化版）
                if self._is_segment_destroyed(current_bis):
                    segment_bis = self.bis[i:j + 1]

                    # 确定线段方向（第一笔的方向）
                    direction = segment_bis[0].direction

                    segment = Segment(
                        start_bi=segment_bis[0],
                        end_bi=segment_bis[-1],
                        direction=direction,
                        bis=segment_bis.copy()
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

        # 简化规则：连续3笔，中间笔的高点低于第一笔和第三笔的高点（向下线段）
        # 或中间笔的低点高于第一笔和第三笔的低点（向上线段）
        if bis[0].direction == Direction.DOWN:  # 向下线段
            return (bis[1].low < bis[0].low and bis[1].low < bis[2].low)
        else:  # 向上线段
            return (bis[1].high > bis[0].high and bis[1].high > bis[2].high)

    def find_zhongshus(self, min_bi_count=3):
        """寻找中枢"""
        if len(self.bis) < min_bi_count:
            return []

        zhongshus = []

        for i in range(len(self.bis) - min_bi_count + 1):
            # 尝试以当前笔开始构建中枢
            for j in range(i + min_bi_count - 1, len(self.bis)):
                candidate_bis = self.bis[i:j + 1]

                # 检查是否构成中枢：至少3笔，且连续笔之间有重叠
                if self._is_zhongshu(candidate_bis):
                    # 计算中枢的ZG, ZD, GG, DD
                    highs = [bi.high for bi in candidate_bis]
                    lows = [bi.low for bi in candidate_bis]

                    # GG: 所有高点中的最高值
                    gg = max(highs)
                    # DD: 所有低点中的最低值
                    dd = min(lows)

                    # 中枢高点ZG: 取连续重叠部分的高点最低值
                    # 中枢低点ZD: 取连续重叠部分的低点最高值
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
                                bis=candidate_bis.copy()
                            )
                            zhongshus.append(zhongshu)

        # 过滤重叠的中枢
        filtered_zhongshus = []
        i = 0
        while i < len(zhongshus):
            current = zhongshus[i]
            filtered_zhongshus.append(current)

            # 跳过与当前中枢重叠的中枢
            j = i + 1
            while j < len(zhongshus):
                next_zs = zhongshus[j]
                # 如果中枢重叠，跳过
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
        if len(bis) < 3:
            return False

        # 检查笔的方向是否交替
        for i in range(len(bis) - 1):
            if bis[i].direction == bis[i + 1].direction:
                return False

        # 简化：检查是否有足够的重叠
        overlap_count = 0
        for i in range(len(bis) - 1):
            bi1 = bis[i]
            bi2 = bis[i + 1]

            # 两笔有重叠
            if bi1.high >= bi2.low and bi2.high >= bi1.low:
                overlap_count += 1

        return overlap_count >= 2  # 至少两个重叠区间

    def detect_divergence(self, fast_period=12, slow_period=26, signal_period=9):
        """检测MACD背驰"""
        if len(self.klines) < slow_period:
            return []

        # 计算MACD
        closes = [k.close for k in self.klines]
        df = pd.DataFrame({'close': closes})

        # 计算EMA
        df['ema_fast'] = df['close'].ewm(span=fast_period, adjust=False).mean()
        df['ema_slow'] = df['close'].ewm(span=slow_period, adjust=False).mean()
        df['diff'] = df['ema_fast'] - df['ema_slow']
        df['dea'] = df['diff'].ewm(span=signal_period, adjust=False).mean()
        df['macd'] = (df['diff'] - df['dea']) * 2

        divergences = []

        # 检测顶背驰
        for i in range(len(self.bis) - 1):
            current_bi = self.bis[i]
            next_bi = self.bis[i + 1]

            # 检查是否是同向笔
            if current_bi.direction == next_bi.direction == Direction.UP:
                # 价格创新高，但MACD未创新高
                price_higher = next_bi.high > current_bi.high

                # 获取笔结束位置的MACD值
                current_macd = df['macd'].iloc[current_bi.end_fractal.index]
                next_macd = df['macd'].iloc[next_bi.end_fractal.index]

                macd_lower = next_macd < current_macd

                if price_higher and macd_lower:
                    divergences.append({
                        'type': '顶背驰',
                        '位置': f"笔{i + 1}->笔{i + 2}",
                        '价格变化': f"{current_bi.high:.2f}->{next_bi.high:.2f}",
                        'MACD变化': f"{current_macd:.4f}->{next_macd:.4f}"
                    })

        return divergences

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
        for f in fractals[:5]:  # 显示前5个分型
            print(f"  {f}")

        # 划分笔
        bis = self.find_bis()
        print(f"划分笔数量: {len(bis)}")
        for bi in bis[:5]:  # 显示前5笔
            print(f"  {bi}, 长度:{bi.length}, 涨幅:{bi.price_change:.2f}")

        # 寻找中枢
        zhongshus = self.find_zhongshus()
        print(f"找到中枢数量: {len(zhongshus)}")
        for zs in zhongshus:
            print(f"  {zs}")

        # 检测背驰
        divergences = self.detect_divergence()
        print(f"检测到背驰数量: {len(divergences)}")
        for d in divergences:
            print(f"  {d['type']}: {d['位置']}")

        return {
            'fractals': fractals,
            'bis': bis,
            'zhongshus': zhongshus,
            'divergences': divergences
        }

    def plot_analysis(self, start_idx=0, end_idx=None):
        """可视化分析结果"""
        if end_idx is None:
            end_idx = len(self.klines)

        # 准备数据
        dates = [k.date for k in self.klines[start_idx:end_idx]]
        highs = [k.high for k in self.klines[start_idx:end_idx]]
        lows = [k.low for k in self.klines[start_idx:end_idx]]
        opens = [k.open for k in self.klines[start_idx:end_idx]]
        closes = [k.close for k in self.klines[start_idx:end_idx]]

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 10),
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
                         color=color, linewidth=2, label='笔' if bi == self.bis[0] else "")

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
                    linewidth=1,
                    edgecolor='purple',
                    facecolor='yellow',
                    alpha=0.3
                )
                ax1.add_patch(rect)

                # 标注中枢
                ax1.text((x_start + x_end) / 2, (zs.zg + zs.zd) / 2,
                         f'ZS\nZG:{zs.zg:.2f}\nZD:{zs.zd:.2f}',
                         ha='center', va='center', fontsize=8,
                         bbox=dict(boxstyle="round,pad=0.3", facecolor="yellow", alpha=0.5))

        ax1.set_title('缠论分析图', fontsize=16, fontweight='bold')
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
                 label='DIFF', linewidth=1)
        ax2.plot(range(len(dea_values)), dea_values, color='orange',
                 label='DEA', linewidth=1)

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


# 使用示例
def generate_sample_data(num_bars=200):
    """生成示例数据"""
    np.random.seed(42)

    dates = pd.date_range(start='2024-01-01', periods=num_bars, freq='D')
    base_price = 100

    prices = [base_price]
    for i in range(1, num_bars):
        # 模拟趋势和波动
        trend = 0.1 if i < 80 else -0.08 if i < 160 else 0.05
        noise = np.random.normal(0, 1)
        change = trend + noise * 0.5

        new_price = prices[-1] * (1 + change / 100)
        prices.append(new_price)

    # 生成OHLC数据
    data = []
    for i in range(num_bars):
        close = prices[i]
        open = close * (1 + np.random.normal(0, 0.5) / 100)
        high = max(open, close) * (1 + abs(np.random.normal(0, 0.5)) / 100)
        low = min(open, close) * (1 - abs(np.random.normal(0, 0.5)) / 100)
        volume = np.random.randint(10000, 100000)

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
    # 生成示例数据
    print("生成示例数据...")
    df = generate_sample_data(150)
    print(f"数据形状: {df.shape}")
    print(df.head())

    # 创建分析器
    analyzer = ChanLunAnalyzer()

    # 添加数据
    analyzer.add_klines_from_dataframe(df)

    # 执行分析
    results = analyzer.analyze()

    # 可视化结果
    print("\n生成分析图表...")
    analyzer.plot_analysis(0, 150)

    # 输出分析报告
    print("\n" + "=" * 50)
    print("缠论分析报告")
    print("=" * 50)

    print(f"\n1. 市场结构分析:")
    print(f"   笔数量: {len(results['bis'])}")
    print(f"   中枢数量: {len(results['zhongshus'])}")

    if results['bis']:
        last_bi = results['bis'][-1]
        print(f"   当前笔方向: {last_bi.direction.name}")
        print(f"   当前笔长度: {last_bi.length}根K线")
        print(f"   当前笔幅度: {last_bi.price_change:.2f}")

    print(f"\n2. 背驰检测:")
    if results['divergences']:
        for d in results['divergences'][-3:]:  # 显示最近的3个背驰
            print(f"   {d['type']}出现在{d['位置']}")
            print(f"   价格变化: {d['价格变化']}")
            print(f"   MACD变化: {d['MACD变化']}")
    else:
        print("   未检测到明显背驰信号")

    print(f"\n3. 交易建议:")
    if results['bis']:
        current_direction = results['bis'][-1].direction
        if current_direction == Direction.UP:
            print("   当前处于向上笔，可关注回调后的买入机会")
        else:
            print("   当前处于向下笔，建议观望或轻仓操作")

        if results['divergences']:
            last_div = results['divergences'][-1]
            if last_div['type'] == '顶背驰':
                print("   注意：近期出现顶背驰，上涨动能可能衰竭")
            elif last_div['type'] == '底背驰':
                print("   注意：近期出现底背驰，下跌动能可能衰竭")

    print("\n4. 风险提示:")
    print("   缠论分析为技术分析工具，仅供参考")
    print("   实际交易需结合基本面、资金管理等多方面因素")
    print("   市场有风险，投资需谨慎")


if __name__ == "__main__":
    main()