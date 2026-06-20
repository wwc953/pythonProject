# A股每日数据收集器

## 功能说明

自动收集全市场A股每日收盘数据，包含：
- 收盘价
- 动态市盈率
- 静态市盈率（PE）
- 涨幅

## 文件结构

```
pythonProject2/
├── daily_a_share_collector.py  # 主收集脚本
├── scheduler.py                 # APScheduler定时调度器
├── run_collector.bat            # 手动执行（双击运行）
├── start_scheduler.bat          # 启动定时任务（双击运行）
├── data/                        # 数据输出目录
│   └── A股每日数据_20260620.xlsx
├── logs/                        # 日志目录
│   └── collector_20260620_140200.log
└── requirements.txt             # 依赖列表
```

## 使用方法

### 方法1：手动收集（推荐先测试）

双击 `run_collector.bat` 或运行：
```bash
python daily_a_share_collector.py
```

### 方法2：启动定时任务（自动收集）

双击 `start_scheduler.bat` 或运行：
```bash
python scheduler.py
```

定时任务会在 **每周一至周五 15:30** 自动执行，自动跳过节假日。

按 `Ctrl+C` 停止调度器。

## 定时任务配置

- **执行时间**：每周一至周五 15:30
- **节假日处理**：使用 chinese-calendar 库自动识别并跳过
- **延迟容忍**：如果任务错过，5分钟内仍会执行一次

## 输出文件

- **位置**：`data/A股每日数据_YYYYMMDD.xlsx`
- **格式**：Excel文件，包含6个字段
- **示例**：`data/A股每日数据_20260620.xlsx`

## 依赖安装

```bash
pip install -r requirements.txt
```

新增依赖：
- `apscheduler`：定时任务调度
- `chinese-calendar`：中国工作日判断

## 注意事项

1. **交易时间**：A股交易时间为 9:30-15:00，15:30收集确保数据完整
2. **执行耗时**：每次任务约2-3分钟（获取静态PE需逐只查询）
3. **数据量**：约5000只股票
4. **日志记录**：每次执行都会生成日志文件在 `logs/` 目录

## 常见问题

### Q: 如何测试脚本是否正常？
A: 直接运行 `python daily_a_share_collector.py`，检查是否有错误日志。

### Q: 如何停止定时任务？
A: 在运行调度器的窗口按 `Ctrl+C`，或直接关闭窗口。

### Q: 如何设置开机自启？
A: 将 `start_scheduler.bat` 放入Windows启动文件夹：
- 按 `Win+R`，输入 `shell:startup`
- 创建快捷方式指向 `start_scheduler.bat`

### Q: 节假日会收集数据吗？
A: 不会。脚本使用 `chinese-calendar` 库判断，会自动跳过周末和法定节假日。
