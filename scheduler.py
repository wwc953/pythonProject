#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A股数据定时调度器
使用 APScheduler 每天15:30自动收集数据
"""

import logging
import sys
import os
from datetime import datetime

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

# 导入主收集模块
from daily_a_share_collector import main_collection, setup_logging


def scheduled_job():
    """定时任务入口"""
    logger = logging.getLogger(__name__)
    try:
        logger.info("定时任务触发，开始执行数据收集...")
        main_collection()
        logger.info("定时任务执行完成")
    except Exception as e:
        logger.error(f"定时任务执行失败: {e}", exc_info=True)


def start_scheduler():
    """启动调度器"""
    logger = setup_logging()
    logger.info("=" * 60)
    logger.info("启动A股数据定时调度器")
    logger.info("=" * 60)
    logger.info("调度规则：每周一至周五 15:30 执行")
    logger.info("按 Ctrl+C 停止调度器")
    logger.info("=" * 60)

    scheduler = BlockingScheduler()

    # 配置定时任务：每周一至周五 15:30 执行
    scheduler.add_job(
        scheduled_job,
        trigger=CronTrigger(
            day_of_week="mon-fri",  # 周一至周五
            hour=15,
            minute=30,
            second=0
        ),
        id="daily_a_share_collection",
        name="每日A股数据收集",
        misfire_grace_time=300,  # 允许5分钟延迟（应对重启等情况）
        coalesce=True,  # 合并错过的任务（只执行一次）
        max_instances=1  # 同时只允许一个实例运行
    )

    # 显示下次执行时间
    jobs = scheduler.get_jobs()
    if jobs:
        next_run = jobs[0].next_run_time
        logger.info(f"下次执行时间: {next_run.strftime('%Y-%m-%d %H:%M:%S')}")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("调度器已停止")
    except Exception as e:
        logger.error(f"调度器异常: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    start_scheduler()
