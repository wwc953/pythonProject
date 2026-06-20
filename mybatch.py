import akshare as ak
import pandas as pd
import time
import logging
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── 可调参数 ──────────────────────────────────────────────
MAX_WORKERS = 8          # 并发线程数
RETRY_COUNT = 3          # 单只股票失败重试次数
RETRY_DELAY = 1.0        # 重试间隔（秒）
REQUEST_DELAY = 0.05     # 每次请求间隔，避免被限流（秒）
# ──────────────────────────────────────────────────────────


def query_one_detail(symbol: str, token: Optional[str] = None) -> Optional[dict]:
    """
    查询单只股票详情，带重试机制。

    Args:
        symbol: 股票代码，如 '002223'
        token: 雪球 xq_a_token（可选），过期时传入新 token

    Returns:
        成功返回股票信息字典，失败（如北交所股票或网络错误）返回 None
    """
    if symbol.upper().startswith("BJ"):
        return None

    for attempt in range(1, RETRY_COUNT + 1):
        try:
            if REQUEST_DELAY > 0:
                time.sleep(REQUEST_DELAY)

            kwargs = {"symbol": symbol.upper()}
            if token:
                kwargs["token"] = token
            df = ak.stock_individual_spot_xq(**kwargs)
            data = dict(zip(df["item"], df["value"]))

            return {
                "代码": data["代码"],
                "名称": data["名称"],
                "收盘价": data["现价"],
                "流通市值(亿元)": round(data["流通值"] / 100_000_000, 2),
                "市盈率(TTM)": data["市盈率(TTM)"],
                "股息率(TTM)%": data["股息率(TTM)"],
                "每股收益": data["每股收益"],
                "今年以来涨幅": data["今年以来涨幅"],
                "时间": data["时间"],
            }
        except Exception as e:
            logger.warning(
                f"[{symbol}] 第 {attempt}/{RETRY_COUNT} 次尝试失败: {e}"
            )
            if attempt < RETRY_COUNT:
                time.sleep(RETRY_DELAY)

    logger.error(f"[{symbol}] 已达最大重试次数，跳过")
    return None


def fetch_all_stocks(
    max_workers: int = MAX_WORKERS,
    token: Optional[str] = None,
) -> list[dict]:
    """
    并发获取所有 A 股详细行情数据。

    Args:
        max_workers: 并发线程数
        token: 雪球 xq_a_token（可选），过期时传入

    Returns:
        各股票信息字典组成的列表
    """
    # 1. 获取股票列表
    logger.info("正在获取 A 股股票列表...")
    stock_list = ak.stock_zh_a_spot()
    total = len(stock_list)
    logger.info(f"共 {total} 只股票，开始并发查询（{max_workers} 线程）...")

    # 2. 并发查询
    results: list[dict] = []
    done = 0
    failed = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_code = {
            executor.submit(query_one_detail, row["代码"], token): row["代码"]
            for _, row in stock_list.iterrows()
        }

        for future in as_completed(future_to_code):
            code = future_to_code[future]
            done += 1
            try:
                info = future.result()
                if info is not None:
                    results.append(info)
                else:
                    failed += 1
            except Exception as e:
                failed += 1
                logger.error(f"[{code}] 未捕获的异常: {e}")

            # 每 50 只打印一次进度
            if done % 50 == 0 or done == total:
                logger.info(f"进度: {done}/{total}（失败 {failed}）")

    logger.info(f"查询完成: 成功 {len(results)} / 总计 {total}")
    return results


def save_to_excel(data: list[dict], filename: Optional[str] = None) -> pd.DataFrame:
    """
    将股票数据保存到 Excel。

    Args:
        data: 股票信息字典列表
        filename: 自定义文件名（不含扩展名），为空则自动生成

    Returns:
        整理后的 DataFrame
    """
    if not data:
        logger.warning("没有数据可保存")
        return pd.DataFrame()

    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"batch_数据_{timestamp}.xlsx"

    df = pd.DataFrame(data)
    df = df.sort_values("流通市值(亿元)", ascending=False)
    df.to_excel(filename, index=False, engine="openpyxl")
    logger.info(f"数据已保存到: {filename}（{len(df)} 条记录）")

    return df


if __name__ == "__main__":
    # 如果 token 过期，在这里传入新的雪球 token:
    #   浏览器打开 https://xueqiu.com → F12 → Cookies → 复制 xq_a_token 的值
    # 然后取消下面一行的注释:
    # TOKEN = "你的xq_a_token"
    TOKEN = None

    stock_data = fetch_all_stocks(token=TOKEN)
    save_to_excel(stock_data)
