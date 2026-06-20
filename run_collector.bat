@echo off
chcp 65001 >nul 2>&1
cd /d D:\code\py\pythonProject2
echo ========================================
echo A股数据收集器 - 手动执行
echo ========================================
python daily_a_share_collector.py
echo.
echo ========================================
echo 执行完成！
echo 数据保存在 data\ 目录
echo ========================================
pause
