# 基本使用
from chanlun_v1 import ChanLunAnalyzer

# 创建分析器
analyzer = ChanLunAnalyzer()

df=ChanLunAnalyzer.generate_sample_data_with_trends(300);
# 添加数据（支持DataFrame）
analyzer.add_klines_from_dataframe(df)

# 执行分析
results = analyzer.analyze()

# 可视化
analyzer.plot_analysis(start_idx=0, end_idx=100)

# 获取具体结果
fractals = analyzer.fractals  # 分型列表
bis = analyzer.bis           # 笔列表
zhongshus = analyzer.zhongshus  # 中枢列表

# 背驰检测
divergences = analyzer.detect_divergence()

# 自定义参数
analyzer.find_zhongshus(min_bi_count=3)  # 修改中枢最小笔数

# 导出分析结果
import json
results_dict = {
    'fractals': [(f.index, f.price, f.type.name) for f in analyzer.fractals],
    'bis': [(bi.start_fractal.index, bi.end_fractal.index, bi.direction.name)
            for bi in analyzer.bis],
    'zhongshus': [(zs.start_index, zs.end_index, zs.zg, zs.zd)
                  for zs in analyzer.zhongshus]
}