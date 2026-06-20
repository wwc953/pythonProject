#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A股每日数据收集器
每天下午3:30自动收集全市场A股数据：收盘价、动态市盈率、静态PE、涨幅
"""

import akshare as ak
import pandas as pd
import numpy as np
import time
import logging
import os
import sys
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, Dict, List
from functools import wraps

# 尝试导入 chinese-calendar，如果失败则使用简单判断
try:
    import chinese_calendar as cc
    HAS_CHINESE_CALENDAR = True
except ImportError:
    HAS_CHINESE_CALENDAR = False
    print("警告：未安装 chinese-calendar，使用简单工作日判断。建议运行：pip install chinese-calendar")


# ============================================================================
# 代理配置 - 解决 ProxyError 问题
# ============================================================================
import os
import requests

# 代理地址（根据实际情况修改）
# Clash 默认端口：7890
# V2Ray 常见端口：1080, 10808, 7890, 7891
PROXY_URL = os.environ.get('PROXY_URL', 'http://127.0.0.1:7890')

# 全局代理配置
PROXIES = {
    'http': PROXY_URL,
    'https': PROXY_URL
}

logger = logging.getLogger(__name__)
logger.info(f"使用代理: {PROXY_URL}")
# ============================================================================

# ── 配置参数 ──────────────────────────────────────────────
MAX_WORKERS = 8          # 并发线程数
RETRY_COUNT = 3          # 失败重试次数
RETRY_DELAY = 1.0        # 重试间隔（秒）
REQUEST_DELAY = 0.05     # 请求间隔（秒）
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
# ──────────────────────────────────────────────────────────


def setup_logging():
    """配置日志系统"""
    os.makedirs(LOG_DIR, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(LOG_DIR, f"collector_{timestamp}.log")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger(__name__)


# 全局日志对象
logger = setup_logging()


def retry_on_failure(retries=RETRY_COUNT, delay=RETRY_DELAY):
    """重试装饰器，带指数退避"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(1, retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < retries:
                        wait_time = delay * (2 ** (attempt - 1))  # 指数退避
                        logger.warning(f"{func.__name__} 第 {attempt}/{retries} 次尝试失败: {e}，{wait_time:.1f}秒后重试")
                        time.sleep(wait_time)
                    else:
                        logger.error(f"{func.__name__} 重试耗尽，最后错误: {last_exception}")
            return None
        return wrapper
    return decorator


def is_trading_day(date: datetime) -> bool:
    """
    判断是否为交易日
    使用 chinese-calendar 库（如果可用），否则使用简单工作日判断
    """
    # 首先检查是否为周末
    if date.weekday() >= 5:
        return False

    # 如果使用 chinese-calendar，检查是否为工作日
    if HAS_CHINESE_CALENDAR:
        try:
            on, name = cc.is_workday(date, get_name=True)
            if not on:
                logger.info(f"{date.strftime('%Y-%m-%d')} 非交易日（{name}），跳过数据收集")
            return on
        except Exception as e:
            logger.warning(f"chinese-calendar 判断失败: {e}，使用简单工作日判断")

    # 简单判断：周一至周五
    return True


@retry_on_failure(retries=3, delay=2)
def fetch_realtime_data() -> Optional[pd.DataFrame]:
    """
    获取全市场实时行情数据（东方财富）
    包含：代码、名称、最新价、涨跌幅、市盈率-动态

    Returns:
        DataFrame 或 None（失败时）
    """
    logger.info("正在获取全市场实时行情数据...")

    # 使用 requests 直接调用东方财富 API（绕过 akshare 的代理问题）
    url = "https://82.push2.eastmoney.com/api/qt/clist/get"
    params = {
        "pn": "1",
        "pz": "100",
        "po": "1",
        "np": "1",
        "ut": "bd1d9ddb04089700cf9c27f6f7426281",
        "fltt": "2",
        "invt": "2",
        "fid": "f12",
        "fs": "m:0 t:6,m:0 t:80,m:1 t:2,m:1 t:23,m:0 t:81 s:2048",
        "fields": "f2,f3,f4,f12,f14,f15,f16,f17,f18,f20,f21,f23,f62,f115,f128,f136,f152",
    }

    all_data = []
    page = 1
    total = None

    while True:
        params["pn"] = str(page)

        try:
            response = requests.get(url, params=params, proxies=PROXIES, timeout=10)
            response.raise_for_status()
            json_data = response.json()

            if total is None:
                total = json_data.get("data", {}).get("total", 0)
                logger.info(f"总共 {total} 只股票")

            items = json_data.get("data", {}).get("diff", [])
            if not items:
                break

            all_data.extend(items)
            logger.info(f"已获取 {len(all_data)}/{total} 只股票")

            if len(all_data) >= total:
                break

            page += 1
            time.sleep(0.1)  # 避免请求过快

        except Exception as e:
            logger.error(f"获取第 {page} 页失败: {e}")
            break

    if not all_data:
        logger.error("未获取到任何数据")
        return None

    # 转换为 DataFrame
    df = pd.DataFrame(all_data)

    # 重命名列
    column_mapping = {
        "f2": "最新价",
        "f3": "涨跌幅",
        "f4": "涨跌额",
        "f12": "代码",
        "f14": "名称",
        "f15": "最高",
        "f16": "最低",
        "f17": "今开",
        "f18": "昨收",
        "f20": "成交量",
        "f21": "成交额",
        "f23": "市盈率-动态",
        "f62": "市盈率(TTM)",
        "f115": "市盈率(静)",
        "f128": "市净率",
        "f136": "换手率",
        "f152": "量比",
    }

    # 只保留需要的列
    needed_columns = ["f12", "f14", "f2", "f3", "f23", "f115"]
    df = df[[col for col in needed_columns if col in df.columns]]
    df = df.rename(columns={k: v for k, v in column_mapping.items() if k in df.columns})

    # 选择最终输出的列
    output_columns = ["代码", "名称", "收盘价", "涨幅", "动态市盈率", "静态市盈率"]
    df = df.rename(columns={
        "最新价": "收盘价",
        "涨跌幅": "涨幅",
        "市盈率-动态": "动态市盈率",
        "市盈率(静)": "静态市盈率"
    })

    # 数据类型转换
    for col in ["收盘价", "涨幅", "动态市盈率", "静态市盈率"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    logger.info(f"成功获取 {len(df)} 只股票实时行情")
    return df

    # 选择需要的列并重命名
    columns_mapping = {
        "代码": "代码",
        "名称": "名称",
        "最新价": "收盘价",
        "涨跌幅": "涨幅",
        "市盈率-动态": "动态市盈率"
    }

    result = df[list(columns_mapping.keys())].rename(columns=columns_mapping)

    # 数据类型转换
    numeric_columns = ["收盘价", "涨幅", "动态市盈率"]
    for col in numeric_columns:
        result[col] = pd.to_numeric(result[col], errors="coerce")

    # 过滤掉无效数据（如退市股、停牌股）
    result = result.dropna(subset=["收盘价"])
    result = result[result["收盘价"] > 0]

    logger.info(f"成功获取 {len(result)} 只股票实时行情")
    return result


@retry_on_failure(retries=2, delay=0.5)
def fetch_single_pe(symbol: str) -> Optional[Dict]:
    """
    获取单只股票的静态市盈率

    Args:
        symbol: 股票代码

    Returns:
        {"代码": symbol, "静态市盈率": pe_value} 或 None
    """
    try:
        if REQUEST_DELAY > 0:
            time.sleep(REQUEST_DELAY)

        df = ak.stock_a_indicator_lg(symbol=symbol)

        if df is not None and not df.empty:
            # 获取最新一条记录的市盈率
            latest = df.iloc[-1]
            # 字段名可能是 "pe" 或 "pe_ratio"，需要适配
            pe_value = None
            for col_name in ["pe", "pe_ratio", "市盈率"]:
                if col_name in latest.index:
                    pe_value = latest[col_name]
                    break

            if pe_value is not None:
                return {
                    "代码": symbol,
                    "静态市盈率": float(pe_value)
                }
    except Exception as e:
        logger.debug(f"[{symbol}] 获取PE数据失败: {e}")

    return None


def fetch_all_pe_data(symbols: List[str], max_workers: int = MAX_WORKERS) -> pd.DataFrame:
    """
    并发获取所有股票的静态市盈率

    Args:
        symbols: 股票代码列表
        max_workers: 并发线程数

    Returns:
        包含代码和静态市盈率的DataFrame
    """
    total = len(symbols)
    logger.info(f"开始并发获取 {total} 只股票的PE数据（{max_workers}线程）...")

    results = []
    failed = 0
    done = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_symbol = {
            executor.submit(fetch_single_pe, symbol): symbol
            for symbol in symbols
        }

        for future in as_completed(future_to_symbol):
            symbol = future_to_symbol[future]
            done += 1

            try:
                data = future.result()
                if data:
                    results.append(data)
                else:
                    failed += 1
            except Exception as e:
                failed += 1
                logger.debug(f"[{symbol}] PE查询异常: {e}")

            # 每 500 只打印一次进度
            if done % 500 == 0 or done == total:
                logger.info(f"PE进度: {done}/{total}（成功 {len(results)}，失败 {failed}）")

    logger.info(f"PE数据获取完成: 成功 {len(results)}/{total}，失败 {failed}")

    if results:
        return pd.DataFrame(results)
    else:
        return pd.DataFrame(columns=["代码", "静态市盈率"])


def process_data(realtime_df: pd.DataFrame, pe_df: pd.DataFrame) -> pd.DataFrame:
    """
    合并和处理数据

    Args:
        realtime_df: 实时行情数据
        pe_df: 静态PE数据

    Returns:
        合并后的完整数据
    """
    # 合并数据（左连接，保留所有有实时行情的股票）
    merged = realtime_df.merge(pe_df, on="代码", how="left")

    # 数据类型转换
    if "静态市盈率" in merged.columns:
        merged["静态市盈率"] = pd.to_numeric(merged["静态市盈率"], errors="coerce")

    # 按代码排序
    merged = merged.sort_values("代码").reset_index(drop=True)

    # 添加收集时间
    merged["收集时间"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    return merged


def save_to_excel(df: pd.DataFrame, output_dir: str = OUTPUT_DIR) -> str:
    """
    保存数据到Excel

    Args:
        df: 数据DataFrame
        output_dir: 输出目录

    Returns:
        保存的文件路径
    """
    os.makedirs(output_dir, exist_ok=True)

    # 按日期命名文件
    timestamp = datetime.now().strftime("%Y%m%d")
    filename = f"A股每日数据_{timestamp}.xlsx"
    filepath = os.path.join(output_dir, filename)

    # 保存
    df.to_excel(filepath, index=False, engine="openpyxl")
    logger.info(f"数据已保存到: {filepath}（{len(df)} 条记录）")

    return filepath


def main_collection():
    """主收集流程"""
    start_time = time.time()
    logger.info("=" * 60)
    logger.info("开始每日A股数据收集任务")
    logger.info("=" * 60)

    # 检查是否为交易日
    # today = datetime.now()
    # if not is_trading_day(today):
    #     logger.info(f"{today.strftime('%Y-%m-%d')} 非交易日，跳过数据收集")
    #     return

    try:
        # 步骤1：获取实时行情
        realtime_data = fetch_realtime_data()
        if realtime_data is None or realtime_data.empty:
            logger.error("获取实时行情失败，任务终止")
            return

        # 步骤2：获取静态PE
        symbols = realtime_data["代码"].tolist()
        pe_data = fetch_all_pe_data(symbols)

        # 步骤3：处理数据
        final_data = process_data(realtime_data, pe_data)

        # 步骤4：保存
        filepath = save_to_excel(final_data)

        # 统计信息
        elapsed = time.time() - start_time
        logger.info("=" * 60)
        logger.info(f"任务完成！耗时: {elapsed:.1f}秒")
        logger.info(f"数据汇总: {len(final_data)} 只股票")
        logger.info(f"动态市盈率缺失: {final_data['动态市盈率'].isna().sum()} 只")
        logger.info(f"静态市盈率缺失: {final_data['静态市盈率'].isna().sum()} 只")
        logger.info(f"文件路径: {filepath}")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"收集任务失败: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main_collection()
