@echo off
chcp 65001 >nul 2>&1
cd /d D:\code\py\pythonProject2
echo ========================================
echo A股数据定时调度器
echo.
echo 调度规则：每周一至周五 15:30 自动收集
echo 按 Ctrl+C 停止调度器
echo ========================================
echo.
python scheduler.py
