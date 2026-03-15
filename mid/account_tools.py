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

loaded = dotenv.load_dotenv(dotenv_path=".env")
API_KEY = os.getenv("TUSHARE_TOKEN")
print(API_KEY)

# 初始化接口
import tushare as ts
ts.set_token(API_KEY)
pro = ts.pro_api()

# 设置数据分割时间
start_date = os.getenv("start_date")
end_date = os.getenv("end_date")

# 模拟用户交互
from dataclasses import fields

# 用户输入的股票代码列表
print("股票列表：")
stock_list = pro.stock_basic(exchange='', list_status='L', fields='ts_code,name,area,industry')
print(stock_list)
print("参考输入格式：000001.SZ,600519.SH")
User = list(input("请输入股票代码，多个代码用逗号分隔: ").split(","))
print(type(User))
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

# 定义一个将20支股票每天各个数据字段加总的函数，形成新的组合数据
from functools import reduce
def sum_daily_data_reduce(data_list):
    # 确保 data_list 非空
    if not data_list:
        return pd.DataFrame()
    # 将所有 DataFrame 对齐（按列与索引），逐个相加，缺失按0处理
    total = reduce(lambda a, b: a.add(b, fill_value=0), data_list)
    return total
# 创建一个表格，存储每天列表中的数据各个数据字段的和，数据字段采取data_list中第一个元素的股票数据字段
daily_total = sum_daily_data_reduce(data_list)
daily_total.name = 'total'
# 打印结果
print("加总后的数据展示")
print(daily_total.shape)
print(daily_total.head(), daily_total.tail())
'''
# 保存原始数据
if os.path.exists("Transformer+LSTM/Advanced/sketch/integrated_data.csv"):
    os.remove("Transformer+LSTM/Advanced/sketch/integrated_data.csv")
    daily_total.to_csv("Transformer+LSTM/Advanced/sketch/integrated_data.csv", index=False)
else:
    daily_total.to_csv("Transformer+LSTM/Advanced/sketch/integrated_data.csv", index=False)
'''
# daily_total就是我们需要的多资产组合原始数据
# 融合模型改进
'''
"""日线指标"""
开盘价(元)
收盘价(元)
最高价(元)
最低价(元)
涨跌(元)
涨跌幅(%)
前收盘价(元)
均价(元)
成交量(股)
--------------
A股流通市值(元)
成交金额(元)
换手率(%)
总股本(股)
PE市盈率
A股流通股本(股)
PB市净率
PS市销率
PCF市现率
总市值(元)
市盈率TTM
内盘成交量
外盘成交量
DDX
成交量变动率
--------------
MTM(5), MTM(10), MTM(20)
--------------
MA(5), MA(10), MA(20)
--------------
EMA(5), EMA(10), EMA(20)
--------------
DIF
DEA
MACD
ATR
RSI
"""综合指标"""
tr, atr
u, d, au, ad, rs, rsi
ma_12, ma_26, ema_12, ema_26, dif, dif_ma_9, dea, macd
"""表格操作"""
计算成交量变动率并填入Excel表格的第25列 -- df, volume_change_rate
计算所有技术指标：成交量变动率、动量指标（MTM）、移动平均线（MA） -- df
'''

"""
表格数据处理相关
1. 复现相关技术指标计算方式
2. 对原始数据进行处理，计算相关技术指标并填入表格中
"""
# print(daily_total['close'])
def calculate_mtm_indicators(daily_total : pd.DataFrame):
    """
    计算动量指标（MTM）
    MTM = 当日收盘价 - n日前收盘价
    并将结果填入DataFrame的相应列中
    
    参数:
        df: DataFrame
        close_col_index: 收盘价列索引（默认第3列，索引为2）
    
    返回:
        mtm_5, mtm_10, mtm_20: 三个动量指标列表
    """
    close_data = daily_total['close'] # 获取收盘价数据（第3列，索引为2）
    
    mtm_5 = []
    mtm_10 = []
    mtm_20 = []
    
    for i in range(len(close_data)):
        # MTM(5): 需要第6个交易日才能计算（i>=5）
        if i < 5:
            mtm_5.append(np.nan)
        else:
            mtm_5.append(close_data.iloc[i] - close_data.iloc[i-5])
        
        # MTM(10): 需要第11个交易日才能计算（i>=10）
        if i < 10:
            mtm_10.append(np.nan)
        else:
            mtm_10.append(close_data.iloc[i] - close_data.iloc[i-10])
        
        # MTM(20): 需要第21个交易日才能计算（i>=20）
        if i < 20:
            mtm_20.append(np.nan)
        else:
            mtm_20.append(close_data.iloc[i] - close_data.iloc[i-20])
    # 将得到的指标转化为pandas Series，并添加到DataFrame中
    # print(mtm_5[:100])
    daily_total['mtm_5'] = mtm_5
    daily_total['mtm_10'] = mtm_10
    daily_total['mtm_20'] = mtm_20
    return (len(mtm_5), len(mtm_10), len(mtm_20))
'''
print(calculate_mtm_indicators(daily_total))
# print(daily_total.shape)
print("mtm处理后：", daily_total.tail(5))
'''
'''
# 保存mtm处理数据
if os.path.exists("Transformer+LSTM/Advanced/sketch/integrated_data_mtm.csv"):
    os.remove("Transformer+LSTM/Advanced/sketch/integrated_data_mtm.csv")
    daily_total.to_csv("Transformer+LSTM/Advanced/sketch/integrated_data_mtm.csv", index=False)
else:
    daily_total.to_csv("Transformer+LSTM/Advanced/sketch/integrated_data_mtm.csv", index=False)
'''

def calculate_ma_indicators(daily_total : pd.DataFrame):
    """
    计算移动平均线（MA）
    MA = 当日及前n-1个交易日收盘价的平均值
    
    参数:
        df: DataFrame
        close_col_index: 收盘价列索引（默认第3列，索引为2）
    
    返回:
        ma_5, ma_10, ma_20: 三个移动平均线列表
    """
    close_data = daily_total['close'] # 获取收盘价数据（第3列，索引为2）
    
    ma_5 = []
    ma_10 = []
    ma_20 = []
    
    for i in range(len(close_data)):
        # MA(5): 从第5个交易日开始计算（i>=4）
        if i < 4:
            ma_5.append(np.nan)
        else:
            ma_5.append(close_data.iloc[i-4:i+1].mean())
        
        # MA(10): 从第10个交易日开始计算（i>=9）
        if i < 9:
            ma_10.append(np.nan)
        else:
            ma_10.append(close_data.iloc[i-9:i+1].mean())
        
        # MA(20): 从第20个交易日开始计算（i>=19）
        if i < 19:
            ma_20.append(np.nan)
        else:
            ma_20.append(close_data.iloc[i-19:i+1].mean())
    # 将得到的指标转化为pandas Series，并添加到DataFrame中
    # print(mtm_5[:100])
    daily_total['ma_5'] = ma_5
    daily_total['ma_10'] = ma_10
    daily_total['ma_20'] = ma_20
    return (len(ma_5), len(ma_10), len(ma_20))
'''
print(calculate_ma_indicators(daily_total))
# print(daily_total.shape)
print("ma处理后：", daily_total.tail(5))
'''
'''
# 保存ma处理数据
if os.path.exists("Transformer+LSTM/Advanced/sketch/integrated_data_ma.csv"):
    os.remove("Transformer+LSTM/Advanced/sketch/integrated_data_ma.csv")
    daily_total.to_csv("Transformer+LSTM/Advanced/sketch/integrated_data_ma.csv", index=False)
else:
    daily_total.to_csv("Transformer+LSTM/Advanced/sketch/integrated_data_ma.csv", index=False)
'''

def calculate_ema_indicators(daily_total : pd.DataFrame):
    """
    计算指数移动平均线（EMA）
    EMA_t = α * close_t + (1-α) * EMA_{t-1}
    其中 α = 2/(n+1)
    
    参数:
        df: DataFrame
        close_col_index: 收盘价列索引（默认第3列，索引为2）
    
    返回:
        ema_5, ema_10, ema_20: 三个指数移动平均线列表
    """
    close_data = daily_total['close'] # 获取收盘价数据（第3列，索引为2）
    
    ema_5 = []
    ema_10 = []
    ema_20 = []
    
    # 计算平滑因子
    alpha_5 = 2 / (5 + 1)   # α = 2/(n+1)
    alpha_10 = 2 / (10 + 1)
    alpha_20 = 2 / (20 + 1)
    
    for i in range(len(close_data)):
        # EMA(5): 从第5个交易日开始计算
        if i < 4:
            ema_5.append(np.nan)
        elif i == 4:
            # 第5个交易日：EMA = MA(5)
            ema_5.append(close_data.iloc[i-4:i+1].mean())
        else:
            # 从第6个交易日开始：EMA_t = α * close_t + (1-α) * EMA_{t-1}
            prev_ema = ema_5[i-1]
            curr_close = close_data.iloc[i]
            curr_ema = alpha_5 * curr_close + (1 - alpha_5) * prev_ema
            ema_5.append(curr_ema)
        
        # EMA(10): 从第10个交易日开始计算
        if i < 9:
            ema_10.append(np.nan)
        elif i == 9:
            # 第10个交易日：EMA = MA(10)
            ema_10.append(close_data.iloc[i-9:i+1].mean())
        else:
            # 从第11个交易日开始：EMA_t = α * close_t + (1-α) * EMA_{t-1}
            prev_ema = ema_10[i-1]
            curr_close = close_data.iloc[i]
            curr_ema = alpha_10 * curr_close + (1 - alpha_10) * prev_ema
            ema_10.append(curr_ema)
        
        # EMA(20): 从第20个交易日开始计算
        if i < 19:
            ema_20.append(np.nan)
        elif i == 19:
            # 第20个交易日：EMA = MA(20)
            ema_20.append(close_data.iloc[i-19:i+1].mean())
        else:
            # 从第21个交易日开始：EMA_t = α * close_t + (1-α) * EMA_{t-1}
            prev_ema = ema_20[i-1]
            curr_close = close_data.iloc[i]
            curr_ema = alpha_20 * curr_close + (1 - alpha_20) * prev_ema
            ema_20.append(curr_ema)
    # 将得到的指标转化为pandas Series，并添加到DataFrame中
    daily_total['ema_5'] = ema_5
    daily_total['ema_10'] = ema_10
    daily_total['ema_20'] = ema_20
    return (len(ema_5), len(ema_10), len(ema_20))
'''
print(calculate_ema_indicators(daily_total))
# print(daily_total.shape)
print("ema处理后：", daily_total.tail(5))
'''
'''
# 保存ema处理数据
if os.path.exists("Transformer+LSTM/Advanced/sketch/integrated_data_ema.csv"):
    os.remove("Transformer+LSTM/Advanced/sketch/integrated_data_ema.csv")
    daily_total.to_csv("Transformer+LSTM/Advanced/sketch/integrated_data_ema.csv", index=False)
else:
    daily_total.to_csv("Transformer+LSTM/Advanced/sketch/integrated_data_ema.csv", index=False)
'''

def calculate_atr_indicators(daily_total : pd.DataFrame):
    """
    计算真实波幅(TR)和平均真实波幅(ATR)指标
    因为这个指标不是日线指标，所以我们另外保存为新的DataFrame
    
    参数:
    df: DataFrame - 包含股票数据的DataFrame
    close_col_index: int - 收盘价列索引(默认第3列，索引为2)
    high_col_index: int - 最高价列索引(默认第4列，索引为3)
    low_col_index: int - 最低价列索引(默认第5列，索引为4)
    n: int - ATR计算周期(默认14日)
    
    返回:
    tr: list - TR指标值列表
    atr: list - ATR指标值列表
    """
    n = int(input("请输入ATR计算周期n（默认14日）: ")) or 14
    close_prices = daily_total['close'].values
    high_prices = daily_total['high'].values
    low_prices = daily_total['low'].values
    
    tr = []
    atr = []
    
    # 计算TR指标
    for i in range(len(daily_total)):
        if i == 0:
            # 第一个交易日TR为NaN
            tr.append(np.nan)
        else:
            # TR = max(High - Low, |High - Close_prev|, |Low - Close_prev|)
            hl = high_prices[i] - low_prices[i]
            hc_prev = abs(high_prices[i] - close_prices[i-1])
            lc_prev = abs(low_prices[i] - close_prices[i-1])
            tr_value = max(hl, hc_prev, lc_prev)
            tr.append(tr_value)
    
    # 计算ATR指标
    for i in range(len(daily_total)):
        if i < n:
            # 前n-1个交易日ATR为NaN
            atr.append(np.nan)
        else:
            # ATR = 该日TR和过去n-1日TR的均值
            tr_values = [tr[j] for j in range(i-n+1, i+1) if not pd.isna(tr[j])]
            if len(tr_values) == n:
                atr_value = sum(tr_values) / n
                atr.append(atr_value)
            else:
                atr.append(np.nan)
    
    # 将tr和atr指标添加到DataFrame中
    daily_total['tr'] = tr
    daily_total['atr'] = atr
    return len(tr), len(atr)

'''
print(calculate_atr_indicators(daily_total))
# print(daily_total.shape)
print("tr和atr处理后：", daily_total.tail(5))
'''
'''
# 保存tr和atr处理数据
if os.path.exists("Transformer+LSTM/Advanced/sketch/integrated_data_tr&atr.csv"):
    os.remove("Transformer+LSTM/Advanced/sketch/integrated_data_tr&atr.csv")
    daily_total.to_csv("Transformer+LSTM/Advanced/sketch/integrated_data_tr&atr.csv", index=False)
else:
    daily_total.to_csv("Transformer+LSTM/Advanced/sketch/integrated_data_tr&atr.csv", index=False)
'''

def calculate_rsi_indicators(daily_total : pd.DataFrame):
    """
    计算相对强弱指数(RSI)指标
    
    参数:
    df: DataFrame - 包含股票数据的DataFrame
    close_col_index: int - 收盘价列索引(默认第3列，索引为2)
    n: int - RSI计算周期(默认14日)
    
    返回:
    u: list - 涨幅Ut列表
    d: list - 跌幅Dt列表
    au: list - 平均涨幅AUt列表
    ad: list - 平均跌幅ADt列表
    rs: list - 相对强弱RS列表
    rsi: list - RSI指标列表
    """
    n = int(input("请输入RSI计算周期n（默认14日）: ")) or 14
    close_prices = daily_total['close'].values
    
    u = []  # 涨幅
    d = []  # 跌幅
    au = [] # 平均涨幅
    ad = [] # 平均跌幅
    rs = [] # 相对强弱
    rsi = [] # RSI
    
    # 计算每日涨幅Ut和跌幅Dt
    for i in range(len(daily_total)):
        if i == 0:
            # 第一个交易日没有前一日价格，设为NaN
            u.append(np.nan)
            d.append(np.nan)
        else:
            price_change = close_prices[i] - close_prices[i-1]
            # Ut = max(Pt - Pt-1, 0)
            ut = max(price_change, 0)
            # Dt = max(Pt-1 - Pt, 0)
            dt = max(-price_change, 0)
            u.append(ut)
            d.append(dt)
    
    # 计算平均涨跌幅AUt和ADt
    for i in range(len(daily_total)):
        if i < n:
            # 前n个交易日AU和AD为NaN
            au.append(np.nan)
            ad.append(np.nan)
        elif i == n:
            # 第n+1个交易日(索引为n)，使用前n个交易日的简单平均
            u_values = [u[j] for j in range(1, i+1) if not pd.isna(u[j])]
            d_values = [d[j] for j in range(1, i+1) if not pd.isna(d[j])]
            if len(u_values) == n and len(d_values) == n:
                au_value = sum(u_values) / n
                ad_value = sum(d_values) / n
                au.append(au_value)
                ad.append(ad_value)
            else:
                au.append(np.nan)
                ad.append(np.nan)
        else:
            # 后续交易日使用递推公式：AUt = (AUt-1 × (n-1) + Ut) / n
            if not pd.isna(au[i-1]) and not pd.isna(ad[i-1]) and not pd.isna(u[i]) and not pd.isna(d[i]):
                au_value = (au[i-1] * (n-1) + u[i]) / n
                ad_value = (ad[i-1] * (n-1) + d[i]) / n
                au.append(au_value)
                ad.append(ad_value)
            else:
                au.append(np.nan)
                ad.append(np.nan)
    
    # 计算RS和RSI
    for i in range(len(daily_total)):
        if not pd.isna(au[i]) and not pd.isna(ad[i]) and ad[i] != 0:
            # RS = AU / AD
            rs_value = au[i] / ad[i]
            rs.append(rs_value)
            # RSI = RS / (1 + RS) × 100
            rsi_value = rs_value / (1 + rs_value) * 100
            rsi.append(rsi_value)
        else:
            rs.append(np.nan)
            rsi.append(np.nan)
    # 将得到的指标转化为pandas Series，并添加到DataFrame中
    daily_total['u'] = u
    daily_total['d'] = d
    daily_total['au'] = au
    daily_total['ad'] = ad
    daily_total['rs'] = rs
    daily_total['rsi'] = rsi
    return len(u), len(d), len(au), len(ad), len(rs), len(rsi)
'''
print(calculate_rsi_indicators(daily_total))
# print(daily_total.shape)
print("rsi处理后：", daily_total.tail(5))
'''
'''
# 保存rsi处理数据
if os.path.exists("Transformer+LSTM/Advanced/sketch/integrated_data_rsi.csv"):
    os.remove("Transformer+LSTM/Advanced/sketch/integrated_data_rsi.csv")
    daily_total.to_csv("Transformer+LSTM/Advanced/sketch/integrated_data_rsi.csv", index=False)
else:
    daily_total.to_csv("Transformer+LSTM/Advanced/sketch/integrated_data_rsi.csv", index=False)
'''

def calculate_macd_indicators(daily_total : pd.DataFrame):
    """
    计算MACD指标体系
    包括：12日MA、26日MA、12日EMA、26日EMA、DIF、DIF的9日MA、DEA、MACD
    
    参数:
        df: DataFrame
        close_col_index: 收盘价列索引（默认第3列，索引为2）
    
    返回:
        ma_12, ma_26, ema_12, ema_26, dif, dif_ma_9, dea, macd: 八个指标列表
    """
    close_data = daily_total['close'] # 获取收盘价数据（第3列，索引为2）
    
    ma_12 = []
    ma_26 = []
    ema_12 = []
    ema_26 = []
    dif = []
    dif_ma_9 = []
    dea = []
    macd = []
    
    # 计算平滑因子
    alpha_12 = 2 / (12 + 1)  # α = 2/(n+1)
    alpha_26 = 2 / (26 + 1)
    alpha_9 = 2 / (9 + 1)
    
    for i in range(len(close_data)):
        # 1. 计算12日MA
        if i < 11:
            ma_12.append(np.nan)
        else:
            ma_12.append(close_data.iloc[i-11:i+1].mean())
        
        # 2. 计算26日MA
        if i < 25:
            ma_26.append(np.nan)
        else:
            ma_26.append(close_data.iloc[i-25:i+1].mean())
        
        # 3. 计算12日EMA
        if i < 11:
            ema_12.append(np.nan)
        elif i == 11:
            # 第12个交易日：EMA = MA(12)
            ema_12.append(ma_12[i])
        else:
            # 从第13个交易日开始：EMA_t = α * close_t + (1-α) * EMA_{t-1}
            prev_ema = ema_12[i-1]
            curr_close = close_data.iloc[i]
            curr_ema = alpha_12 * curr_close + (1 - alpha_12) * prev_ema
            ema_12.append(curr_ema)
        
        # 4. 计算26日EMA
        if i < 25:
            ema_26.append(np.nan)
        elif i == 25:
            # 第26个交易日：EMA = MA(26)
            ema_26.append(ma_26[i])
        else:
            # 从第27个交易日开始：EMA_t = α * close_t + (1-α) * EMA_{t-1}
            prev_ema = ema_26[i-1]
            curr_close = close_data.iloc[i]
            curr_ema = alpha_26 * curr_close + (1 - alpha_26) * prev_ema
            ema_26.append(curr_ema)
        
        # 5. 计算DIF = EMA_12 - EMA_26
        if i < 25 or pd.isna(ema_12[i]) or pd.isna(ema_26[i]):
            dif.append(np.nan)
        else:
            dif.append(ema_12[i] - ema_26[i])
        
        # 6. 计算DIF的9日MA
        if i < 33:  # 需要9个有效的DIF值，从第34个交易日开始
            dif_ma_9.append(np.nan)
        else:
            # 取前9个DIF值计算平均
            dif_values = [dif[j] for j in range(i-8, i+1) if not pd.isna(dif[j])]
            if len(dif_values) == 9:
                dif_ma_9.append(np.mean(dif_values))
            else:
                dif_ma_9.append(np.nan)
        
        # 7. 计算DEA（DIF的9日EMA）
        if i < 33:
            dea.append(np.nan)
        elif i == 33:
            # 第34个交易日：DEA = DIF的9日MA
            dea.append(dif_ma_9[i])
        else:
            # 从第35个交易日开始：DEA_t = α * DIF_t + (1-α) * DEA_{t-1}
            if not pd.isna(dif[i]) and not pd.isna(dea[i-1]):
                prev_dea = dea[i-1]
                curr_dif = dif[i]
                curr_dea = alpha_9 * curr_dif + (1 - alpha_9) * prev_dea
                dea.append(curr_dea)
            else:
                dea.append(np.nan)
        
        # 8. 计算MACD = 2 * (DIF - DEA)
        if pd.isna(dif[i]) or pd.isna(dea[i]):
            macd.append(np.nan)
        else:
            macd.append(2 * (dif[i] - dea[i]))
    # 将得到的指标转化为pandas Series，并添加到DataFrame中
    daily_total['ma_12'] = ma_12
    daily_total['ma_26'] = ma_26
    daily_total['ema_12'] = ema_12
    daily_total['ema_26'] = ema_26
    daily_total['dif'] = dif
    daily_total['dif_ma_9'] = dif_ma_9
    daily_total['dea'] = dea
    return len(ma_12), len(ma_26), len(ema_12), len(ema_26), len(dif), len(dif_ma_9), len(dea), len(macd)


'''
print(calculate_macd_indicators(daily_total))
# print(daily_total.shape)
print("macd处理后：", daily_total.tail(5))
'''
'''
# 保存macd处理数据
if os.path.exists("Transformer+LSTM/Advanced/sketch/integrated_data_macd.csv"):
    os.remove("Transformer+LSTM/Advanced/sketch/integrated_data_macd.csv")
    daily_total.to_csv("Transformer+LSTM/Advanced/sketch/integrated_data_macd.csv", index=False)
else:
    daily_total.to_csv("Transformer+LSTM/Advanced/sketch/integrated_data_macd.csv", index=False)
'''

def calculate_volume_change_rate(daily_total : pd.DataFrame):
    """
    计算成交量变动率并填入Excel表格的第25列
    
    参数:
        daily_total: DataFrame - 包含股票数据的DataFrame
    """
    
    # 获取成交量数据（第10列，索引为9）
    volume_data = daily_total['vol']
    
    # print(f"成交量数据前5个值: {volume_data.head()}")
    
    # 计算成交量变动率
    volume_change_rate = []
    
    for i in range(len(volume_data)):
        if i == 0:
            # 第一个交易日没有前一日数据，用NaN填充
            volume_change_rate.append(np.nan)
        else:
            # 计算相对前一交易日的变动率
            prev_volume = volume_data.iloc[i-1]
            curr_volume = volume_data.iloc[i]
            
            if prev_volume == 0 or pd.isna(prev_volume):
                # 如果前一日成交量为0或NaN，用NaN填充
                volume_change_rate.append(np.nan)
            else:
                # 变动率 = (当前成交量 - 前一日成交量) / 前一日成交量
                change_rate = (curr_volume - prev_volume) / prev_volume
                volume_change_rate.append(change_rate)
    
    # 将成交量变动率填入第25列
    daily_total['volume_change_rate'] = volume_change_rate
    return len(volume_change_rate)

'''
print(calculate_volume_change_rate(daily_total))
# print(daily_total.shape)
print("成交量变动率处理后：", daily_total.tail(5))
'''

"""保存成交量变动率处理数据"""
def save_data(data : pd.DataFrame):
    folder_path = input("请输入保存路径（默认当前路径）: ") or "Transformer+LSTM/Advanced/data"
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
    calculate_mtm_indicators(data)
    calculate_ma_indicators(data)
    calculate_ema_indicators(data)
    calculate_atr_indicators(data)
    calculate_rsi_indicators(data)
    calculate_macd_indicators(data)
    calculate_volume_change_rate(data)
    save_data(data)

# 保存多资产组合数据
calculate_mtm_indicators(daily_total)
calculate_ma_indicators(daily_total)
calculate_ema_indicators(daily_total)
calculate_atr_indicators(daily_total)
calculate_rsi_indicators(daily_total)
calculate_macd_indicators(daily_total)
calculate_volume_change_rate(daily_total)
save_data(daily_total)