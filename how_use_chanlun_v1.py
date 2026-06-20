"""
缠论分析器 - 完整使用示例
============================
演示 ChanLunAnalyzer 的全部 API，包括：
  - 数据导入（手动添加 / DataFrame / 生成模拟数据）
  - 分型 → 笔 → 线段 → 中枢 完整分析流程
  - 背驰检测
  - 可视化
  - 结果导出为 JSON
"""

import json
from chanlun_v1 import ChanLunAnalyzer, Direction, generate_sample_data


# ============================================================
# 1. 数据导入
# ============================================================

def demo_add_kline_manually():
    """逐根添加 K 线（适合实时行情逐条推送的场景）"""
    analyzer = ChanLunAnalyzer()
    analyzer.add_kline(
        date='2024-01-02',
        high=105.0,
        low=98.0,
        open=100.0,
        close=103.0,
        volume=50000,
    )
    # ... 实际场景中每来一根新 K 线就调用一次 add_kline
    return analyzer


def demo_add_from_dataframe():
    """从 DataFrame 批量导入（适合回测 / 历史数据）"""
    df = generate_sample_data(num_bars=300)
    analyzer = ChanLunAnalyzer()
    analyzer.add_klines_from_dataframe(df)
    return analyzer


# ============================================================
# 2. 完整分析流程
# ============================================================

def run_full_analysis(analyzer: ChanLunAnalyzer):
    """
    依次执行缠论分析的四个核心步骤：
      ① 包含关系处理
      ② 分型识别
      ③ 笔划分
      ④ 线段划分
      ⑤ 中枢识别
      ⑥ 背驰检测
    """
    # ① 处理 K 线包含关系
    analyzer.process_containing_relationship()
    print(f"  原始 K 线: {len(analyzer.klines)}  →  合并后: {len(analyzer.merged_klines)}")

    # ② 寻找分型
    fractals = analyzer.find_fractals()
    print(f"  分型数量: {len(fractals)}")
    for f in fractals[:8]:
        print(f"    {f}")

    # ③ 划分笔
    bis = analyzer.find_bis()
    print(f"  笔数量: {len(bis)}")
    for bi in bis[:8]:
        print(f"    {bi}  长度:{bi.length}根K线  幅度:{bi.price_change:.2f}")

    # ④ 划分线段
    segments = analyzer.find_segments()
    print(f"  线段数量: {len(segments)}")
    for seg in segments[:5]:
        print(f"    {seg}")

    # ⑤ 寻找中枢（默认最小 3 笔）
    zhongshus = analyzer.find_zhongshus(min_bi_count=3)
    print(f"  中枢数量: {len(zhongshus)}")
    for zs in zhongshus:
        print(f"    {zs}  中轴:{zs.center:.2f}")

    # ⑥ 背驰检测（MACD）
    analyzer.divergences = analyzer.detect_divergence()  # type: ignore[attr-defined]
    print(f"  背驰信号: {len(analyzer.divergences)}")  # type: ignore[attr-defined]
    for d in analyzer.divergences:  # type: ignore[attr-defined]
        print(f"    {d['type']} @ {d['位置']}  价格:{d['价格变化']}  MACD:{d['MACD变化']}")


# ============================================================
# 3. 结果导出
# ============================================================

def export_results(analyzer: ChanLunAnalyzer) -> dict:
    """
    将分析结果序列化为 dict（可直接转 JSON）。
    所有 dataclass / Enum 字段均转为基本类型。
    """
    results = {
        'summary': {
            'total_klines': len(analyzer.klines),
            'merged_klines': len(analyzer.merged_klines),
            'total_fractals': len(analyzer.fractals),
            'total_bis': len(analyzer.bis),
            'total_segments': len(analyzer.segments),
            'total_zhongshus': len(analyzer.zhongshus),
        },
        'fractals': [
            {'index': f.index, 'price': f.price, 'type': f.type.name}
            for f in analyzer.fractals
        ],
        'bis': [
            {
                'start': bi.start_fractal.index,
                'end': bi.end_fractal.index,
                'direction': bi.direction.name,
                'high': bi.high,
                'low': bi.low,
                'length': bi.length,
                'price_change': round(bi.price_change, 4),
            }
            for bi in analyzer.bis
        ],
        'segments': [
            {
                'start': seg.start_bi.start_fractal.index,
                'end': seg.end_bi.end_fractal.index,
                'direction': seg.direction.name,
                'bi_count': len(seg.bis),
                'high': seg.high,
                'low': seg.low,
            }
            for seg in analyzer.segments
        ],
        'zhongshus': [
            {
                'start_index': zs.start_index,
                'end_index': zs.end_index,
                'zg': zs.zg,
                'zd': zs.zd,
                'gg': zs.gg,
                'dd': zs.dd,
                'center': round(zs.center, 4),
                'bi_count': len(zs.bis),
            }
            for zs in analyzer.zhongshus
        ],
    }
    return results


def print_trading_suggestion(analyzer: ChanLunAnalyzer):
    """根据分析结果输出简易交易建议"""
    print("\n" + "=" * 50)
    print("交易建议")
    print("=" * 50)

    if not analyzer.bis:
        print("  笔数量不足，暂无建议")
        return

    last_bi = analyzer.bis[-1]
    last_direction = last_bi.direction
    trend = "向上" if last_direction == Direction.UP else "向下"
    print(f"  当前趋势: {trend}笔  (长度 {last_bi.length} 根K线)")

    # 中枢判断
    if analyzer.zhongshus:
        last_zs = analyzer.zhongshus[-1]
        closes = [k.close for k in analyzer.klines]
        current_price = closes[-1]
        if current_price > last_zs.zg:
            print(f"  价格已脱离最后中枢（中枢上沿 {last_zs.zg:.2f}），多头延续")
        elif current_price < last_zs.zd:
            print(f"  价格跌破最后中枢（中枢下沿 {last_zs.zd:.2f}），空头延续")
        else:
            print(f"  价格在中枢区间内 [{last_zs.zd:.2f} ~ {last_zs.zg:.2f}]，震荡中")

    # 背驰提示
    if analyzer.divergences:  # type: ignore[attr-defined]
        last_div = analyzer.divergences[-1]  # type: ignore[attr-defined]
        if last_div['type'] == '顶背驰':
            print("  ⚠ 近期出现顶背驰，上涨动能可能衰竭，注意风险")
        elif last_div['type'] == '底背驰':
            print("  ✓ 近期出现底背驰，下跌动能可能衰竭，关注反弹机会")

    # 风险提示
    print("\n  ※ 以上仅为技术面参考，投资有风险，入市需谨慎")


# ============================================================
# 4. 主入口
# ============================================================

def main():
    print("=" * 50)
    print("缠论分析器 - 完整使用示例")
    print("=" * 50)

    # --- 生成模拟数据 ---
    print("\n[1] 生成模拟数据 (300 根 K 线) ...")
    df = generate_sample_data(num_bars=300)
    print(f"    DataFrame shape: {df.shape}")
    print(df.head(3).to_string(index=False))

    # --- 创建分析器并导入数据 ---
    print("\n[2] 创建分析器并导入数据 ...")
    analyzer = ChanLunAnalyzer()
    analyzer.add_klines_from_dataframe(df)

    # --- 执行完整分析 ---
    print("\n[3] 执行缠论分析 ...")
    run_full_analysis(analyzer)

    # --- 导出结果 ---
    print("\n[4] 导出分析结果 ...")
    results_dict = export_results(analyzer)
    print(json.dumps(results_dict['summary'], indent=2, ensure_ascii=False))

    # 可选：保存到文件
    # with open('chanlun_results.json', 'w', encoding='utf-8') as f:
    #     json.dump(results_dict, f, ensure_ascii=False, indent=2)

    # --- 交易建议 ---
    print_trading_suggestion(analyzer)

    # --- 可视化 ---
    print("\n[5] 绘制分析图表 ...")
    try:
        analyzer.plot_analysis(start_idx=0, end_idx=min(200, len(analyzer.klines)))
    except Exception as e:
        print(f"    绘图失败（可能无图形界面）: {e}")

    print("\n✓ 完成！")


if __name__ == "__main__":
    main()
