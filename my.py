import akshare as ak
import pandas as pd
import time
from datetime import datetime


def get_stock_basic_info():
    stock_zh_a_hist_df = ak.stock_zh_a_hist(
        symbol="600436",
        period="daily",
        start_date="20251101",
        end_date="20251116",
        adjust="qfq"
    )
    print(stock_zh_a_hist_df)


def do_query():
    stock_data = []
    # 方法1: 使用akshare获取所有A股股票代码和名称
    stock_info_a_code_name = ak.stock_zh_a_spot()
    print(f"数据: {stock_info_a_code_name}")
    print("开始获取详细数据，这可能需要一些时间...")

    count = 0
    total = len(stock_info_a_code_name)

    for index, row in stock_info_a_code_name.iterrows():
        stock_data.append(query_one_detail(row['代码']))
        count += 1
        # 进度显示
        if count % 50 == 0:
            print(f"已处理 {count}/{total} 只股票...")

        # 添加延时避免请求过于频繁
        time.sleep(0.01)

    print(f"数据收集完成！成功获取 {len(stock_data)} 只股票的数据")
    return stock_data


def save_to_excel(stock_data, filename=None):
    """
    保存数据到Excel文件
    """
    if not filename:
        today = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"A股股票数据_{today}.xlsx"

    if not stock_data:
        print("没有数据可保存")
        return pd.DataFrame()

    df = pd.DataFrame(stock_data)

    # 按流通市值排序
    df = df.sort_values('流通市值(亿元)', ascending=False)

    # 保存到Excel
    df.to_excel(filename, index=False, engine='openpyxl')
    print(f"数据已保存到文件: {filename}")

    return df


def query_one_detail(symbol):
    up = symbol.upper();
    if up.startswith("BJ"):
        return {'代码': up};
    stock_individual_spot_xq_df = ak.stock_individual_spot_xq(up)
    # print(stock_individual_spot_xq_df)
    # 将DataFrame转换为字典，便于多次提取
    data_dict = dict(zip(stock_individual_spot_xq_df['item'], stock_individual_spot_xq_df['value']))
    stock_info = {
        '代码': data_dict['代码'],
        '名称': data_dict['名称'],
        '收盘价': data_dict['现价'],
        '流通市值(亿元)': round(data_dict['流通值'] / 100000000, 2),
        '市盈率(TTM)': data_dict['市盈率(TTM)'],
        '股息率(TTM)%': data_dict['股息率(TTM)'],
        '每股收益': data_dict['每股收益'],
        '今年以来涨幅': data_dict['今年以来涨幅'],
        '时间': data_dict['时间']
    }
    print(stock_info)
    return stock_info;


if __name__ == "__main__":
    # stock_data = [];
    # stock_data.append(query_one_detail('sz002223'));
    # save_to_excel(stock_data)

    # stock_individual_spot_xq_df = ak.stock_individual_spot_xq(symbol="sz301608")
    # print(stock_individual_spot_xq_df)

    # import datetime
    #
    # dt = datetime.datetime.fromtimestamp(1762760076000 / 1000)
    # print(dt.strftime('%Y-%m-%d'))

    save_to_excel(do_query());
