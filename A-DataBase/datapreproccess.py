"""
数据预处理脚本
1. 获取多资产组合的日线数据
2. 计算相关技术指标并填入表格中，包括：
   - 动量指标（MTM）：MTM(5), MTM(10), MTM(20)
   - 移动平均线（MA）：MA(5), MA(10), MA(20)
   - 指数移动平均线（EMA）：EMA(5), EMA(10), EMA(20)
   - 真实波幅（TR）和平均真实波幅（ATR）
   - 相对强弱指数（RSI）：u, d, au, ad, rs, rsi
   - MACD指标体系：ma_12, ma_26, ema_12, ema_26, dif, dif_ma_9, dea, macd
   - 成交量变动率
"""


# ################1.获取并预处理数据
from re import split
import dotenv
import os
import pandas as pd
import numpy as np
import math
import warnings
# warnings.filterwarnings('ignore')

# 导入指标计算工具
from indicator_tools import (
    calculate_mtm_indicators,
    calculate_ma_indicators,
    calculate_ema_indicators,
    calculate_atr_indicators,
    calculate_rsi_indicators,
    calculate_macd_indicators,
    calculate_volume_change_rate,
    apply_all_indicators
)




# =====环境变量加载=====
loaded = dotenv.load_dotenv(dotenv_path=".env")
API_KEY = os.getenv("TUSHARE_TOKEN")
print(f"USER'S TUSHARE_TOKEN: {API_KEY}")
# 设置数据分割时间
start_date = os.getenv("start_date")
end_date = os.getenv("end_date")
print(f"DATA RANGE: {start_date} to {end_date}")



# =====接口配置=====
# 初始化接口
import tushare as ts
ts.set_token(API_KEY)
pro = ts.pro_api()

# 用户输入的股票代码列表
print("股票列表：")
stock_exam = pro.stock_basic(exchange='', list_status='L', fields='ts_code,name,area,industry')
stock_exam.to_csv("front/stock_list.csv", index=False)

print(stock_exam)
for index, row in stock_exam.iterrows():
    print(f"{row['ts_code']}: {row['name']} ({row['industry']})")
print("参考输入格式：000001.SZ,600519.SH")
User = list(input("请输入股票代码，多个代码用逗号分隔: ").split(","))
# 股票池：存放股票代码的列表
ts_code_list = []
# 数据列表
data_list = []

# 由于用户是多资产用户，因此需要获取多个股票的数据
# 函数提取交易所代码，作为tushare的参数之一
def get_exchange_code(ts_code):
    return ts_code.split('.')[1]

# 将用户输入的股票代码添加到股票池中
for code in User:
    ts_code_list.append(code)

# 获取多个股票的日线数据
for stock in ts_code_list:
    data = pro.daily(ts_code=stock, start_date=start_date, end_date=end_date,
                              fields='open, high, low, close, pre_close, change, pct_chg, vol, amount')
    # 给DataFrame添加一个名称属性，便于后续保存
    data.name = stock
    data_list.append(data)
    print(f"Fetched data for {stock}: {data.shape}")
print(f"Total data: {len(data_list)}")


"""保存成交量变动率处理数据"""
def save_data(data: pd.DataFrame):
    folder_path = input("请输入保存路径（默认当前路径）: ") or "A-DataBase\data\1_raw_data"
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
    else:
        file_name = data.name + ".csv"
        file_path = os.path.join(folder_path, file_name)
        if os.path.exists(file_path):
            os.remove(file_path)
        data.to_csv(file_path, index=False)
        print(f"{file_name}保存成功！")


# 保存常规数据
for data in data_list:
    apply_all_indicators(data)
    save_data(data)