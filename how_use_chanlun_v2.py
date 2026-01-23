# 基本使用
from chanlun_v2 import ChanLunAnalyzer

config = {
    'min_bi_length': 4,           # 笔的最小长度
    'min_zs_bi_count': 3,         # 中枢最小笔数
    'divergence_lookback': 20,    # 背驰回溯周期
    'macd_fast': 12,
    'macd_slow': 26,
    'macd_signal': 9
}

# 创建分析器
analyzer = ChanLunAnalyzer(config)

# 添加数据
df=ChanLunAnalyzer.generate_sample_data_with_trends(300);
analyzer.add_klines_from_dataframe(df)

# 执行完整分析
results = analyzer.analyze()

# 获取买卖点
buy_sell_points = analyzer.buy_sell_points
for point in buy_sell_points:
    print(f"{point.type.value}: 价格{point.price:.2f}, 置信度{point.confidence:.2f}")

# 生成交易信号
signals = analyzer.generate_trading_signals()

# 可视化（包含买卖点标注）
analyzer.plot_analysis(show_buy_sell=True)

# 获取详细分析报告
report = analyzer.get_analysis_report()
print(report)
