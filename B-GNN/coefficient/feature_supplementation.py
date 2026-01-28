import pandas as pd
import numpy as np
import os

def calculate_mtm_indicators(df, close_col_index=2):
    """
    计算动量指标（MTM）
    MTM = 当日收盘价 - n日前收盘价
    
    参数:
        df: DataFrame
        close_col_index: 收盘价列索引（默认第3列，索引为2）
    
    返回:
        mtm_5, mtm_10, mtm_20: 三个动量指标列表
    """
    close_data = df.iloc[:, close_col_index]
    
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
    
    return mtm_5, mtm_10, mtm_20

def calculate_ma_indicators(df, close_col_index=2):
    """
    计算移动平均线（MA）
    MA = 当日及前n-1个交易日收盘价的平均值
    
    参数:
        df: DataFrame
        close_col_index: 收盘价列索引（默认第3列，索引为2）
    
    返回:
        ma_5, ma_10, ma_20: 三个移动平均线列表
    """
    close_data = df.iloc[:, close_col_index]
    
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
    
    return ma_5, ma_10, ma_20

def calculate_ema_indicators(df, close_col_index=2):
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
    close_data = df.iloc[:, close_col_index]
    
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
    
    return ema_5, ema_10, ema_20

def calculate_atr_indicators(df, close_col_index=2, high_col_index=3, low_col_index=4, n=14):
    """
    计算真实波幅(TR)和平均真实波幅(ATR)指标
    
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
    close_prices = df.iloc[:, close_col_index].values
    high_prices = df.iloc[:, high_col_index].values
    low_prices = df.iloc[:, low_col_index].values
    
    tr = []
    atr = []
    
    # 计算TR指标
    for i in range(len(df)):
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
    for i in range(len(df)):
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
    
    return tr, atr

def calculate_rsi_indicators(df, close_col_index=2, n=14):
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
    close_prices = df.iloc[:, close_col_index].values
    
    u = []  # 涨幅
    d = []  # 跌幅
    au = [] # 平均涨幅
    ad = [] # 平均跌幅
    rs = [] # 相对强弱
    rsi = [] # RSI
    
    # 计算每日涨幅Ut和跌幅Dt
    for i in range(len(df)):
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
    for i in range(len(df)):
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
    for i in range(len(df)):
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
    
    return u, d, au, ad, rs, rsi

def calculate_macd_indicators(df, close_col_index=2):
    """
    计算MACD指标体系
    包括：12日MA、26日MA、12日EMA、26日EMA、DIF、DIF的9日MA、DEA、MACD
    
    参数:
        df: DataFrame
        close_col_index: 收盘价列索引（默认第3列，索引为2）
    
    返回:
        ma_12, ma_26, ema_12, ema_26, dif, dif_ma_9, dea, macd: 八个指标列表
    """
    close_data = df.iloc[:, close_col_index]
    
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
    
    return ma_12, ma_26, ema_12, ema_26, dif, dif_ma_9, dea, macd

def calculate_volume_change_rate(file_path):
    """
    计算成交量变动率并填入Excel表格的第25列
    
    参数:
        file_path: Excel文件路径
    """
    # 读取Excel文件
    df = pd.read_excel(file_path)
    
    print(f"原始数据形状: {df.shape}")
    print(f"列数: {len(df.columns)}")
    
    # 获取成交量数据（第10列，索引为9）
    volume_col_index = 9  # 第10列
    volume_data = df.iloc[:, volume_col_index]
    
    print(f"成交量列名: {df.columns[volume_col_index]}")
    print(f"成交量数据前5个值: {volume_data.head()}")
    
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
    
    # 确保DataFrame有足够的列
    target_col_index = 24  # 第25列，索引为24
    
    # 如果列数不够，添加空列
    while len(df.columns) <= target_col_index:
        df[f'新增列_{len(df.columns)+1}'] = np.nan
    
    # 将成交量变动率填入第25列
    df.iloc[:, target_col_index] = volume_change_rate
    
    # 更新列名
    df.columns.values[target_col_index] = '成交量变动率'
    
    print(f"\n成交量变动率计算完成:")
    print(f"前10个成交量变动率值: {volume_change_rate[:10]}")
    print(f"非NaN值的数量: {sum(1 for x in volume_change_rate if not pd.isna(x))}")
    print(f"NaN值的数量: {sum(1 for x in volume_change_rate if pd.isna(x))}")
    
    # 直接保存到原文件，覆盖原始数据
    df.to_excel(file_path, index=False)
    
    print(f"\n数据已更新到原文件: {file_path}")
    print(f"更新后数据形状: {df.shape}")
    
    return df, volume_change_rate

def fill_missing_values(df):
    """
    对DataFrame中的每一列进行缺失值填充
    优先使用前向填充，无法前向填充时使用后向填充
    
    参数:
        df: DataFrame
    
    返回:
        df: 填充后的DataFrame
    """
    print("开始缺失值填充...")
    
    # 检查每列的缺失值情况
    missing_info = df.isnull().sum()
    print(f"缺失值统计:\n{missing_info[missing_info > 0]}")
    
    # 对每一列进行缺失值填充
    for col in df.columns:
        if df[col].isnull().any():
            # 先进行前向填充
            df[col] = df[col].fillna(method='ffill')
            # 如果还有缺失值，进行后向填充
            df[col] = df[col].fillna(method='bfill')
    
    # 检查填充后的缺失值情况
    remaining_missing = df.isnull().sum().sum()
    print(f"填充后剩余缺失值数量: {remaining_missing}")
    
    return df

def calculate_log_return(df, close_col_index=2):
    """
    计算对数收益率
    对数收益率 = ln(第t日收盘价/第t-1日收盘价)
    
    参数:
        df: DataFrame
        close_col_index: 收盘价列索引（默认第3列，索引为2）
    
    返回:
        log_return: 对数收益率列表
    """
    close_data = df.iloc[:, close_col_index]
    log_return = []
    
    for i in range(len(close_data)):
        if i == 0:
            # 第一个交易日无法计算对数收益率
            log_return.append(np.nan)
        else:
            prev_close = close_data.iloc[i-1]
            curr_close = close_data.iloc[i]
            
            if prev_close <= 0 or curr_close <= 0 or pd.isna(prev_close) or pd.isna(curr_close):
                # 如果价格为负数、零或NaN，无法计算对数收益率
                log_return.append(np.nan)
            else:
                # 计算对数收益率
                log_ret = np.log(curr_close / prev_close)
                log_return.append(log_ret)
    
    return log_return

def calculate_all_indicators(file_path):
    """
    计算所有技术指标：成交量变动率、动量指标（MTM）、移动平均线（MA）、对数收益率
    
    参数:
        file_path: Excel文件路径
    """
    # 读取Excel文件
    df = pd.read_excel(file_path)
    
    print(f"\n处理文件: {file_path}")
    print(f"原始数据形状: {df.shape}")
    print(f"列数: {len(df.columns)}")
    
    # 1. 缺失值填充
    df = fill_missing_values(df)
    
    # 1. 计算成交量变动率（第25列）
    volume_col_index = 9  # 第10列
    volume_data = df.iloc[:, volume_col_index]
    
    volume_change_rate = []
    for i in range(len(volume_data)):
        if i == 0:
            volume_change_rate.append(np.nan)
        else:
            prev_volume = volume_data.iloc[i-1]
            curr_volume = volume_data.iloc[i]
            
            if prev_volume == 0 or pd.isna(prev_volume):
                volume_change_rate.append(np.nan)
            else:
                change_rate = (curr_volume - prev_volume) / prev_volume
                volume_change_rate.append(change_rate)
    
    # 2. 计算动量指标（MTM）
    mtm_5, mtm_10, mtm_20 = calculate_mtm_indicators(df)
    
    # 3. 计算移动平均线（MA）
    ma_5, ma_10, ma_20 = calculate_ma_indicators(df)
    
    # 4. 计算指数移动平均线（EMA）
    ema_5, ema_10, ema_20 = calculate_ema_indicators(df)
    
    # 5. 计算MACD指标体系
    ma_12, ma_26, ema_12, ema_26, dif, dif_ma_9, dea, macd = calculate_macd_indicators(df)
    
    # 6. 计算ATR指标
    tr, atr = calculate_atr_indicators(df)
    
    # 7. 计算RSI指标
    u, d, au, ad, rs, rsi = calculate_rsi_indicators(df)
    
    # 8. 计算对数收益率
    log_return = calculate_log_return(df)
    
    # 确保DataFrame有足够的列（到第51列）
    target_cols = 51
    while len(df.columns) < target_cols:
        df[f'新增列_{len(df.columns)+1}'] = np.nan
    
    # 填入各项指标
    df.iloc[:, 24] = volume_change_rate  # 第25列：成交量变动率
    df.iloc[:, 25] = mtm_5              # 第26列：MTM(5)
    df.iloc[:, 26] = mtm_10             # 第27列：MTM(10)
    df.iloc[:, 27] = mtm_20             # 第28列：MTM(20)
    df.iloc[:, 28] = ma_5               # 第29列：MA(5)
    df.iloc[:, 29] = ma_10              # 第30列：MA(10)
    df.iloc[:, 30] = ma_20              # 第31列：MA(20)
    df.iloc[:, 31] = ema_5              # 第32列：EMA(5)
    df.iloc[:, 32] = ema_10             # 第33列：EMA(10)
    df.iloc[:, 33] = ema_20             # 第34列：EMA(20)
    df.iloc[:, 34] = ma_12              # 第35列：MA(12)
    df.iloc[:, 35] = ma_26              # 第36列：MA(26)
    df.iloc[:, 36] = ema_12             # 第37列：EMA(12)
    df.iloc[:, 37] = ema_26             # 第38列：EMA(26)
    df.iloc[:, 38] = dif                # 第39列：DIF
    df.iloc[:, 39] = dif_ma_9           # 第40列：DIF的9日MA
    df.iloc[:, 40] = dea                # 第41列：DEA
    df.iloc[:, 41] = macd               # 第42列：MACD
    df.iloc[:, 42] = tr                 # 第43列：TR
    df.iloc[:, 43] = atr                # 第44列：ATR
    df.iloc[:, 44] = u                  # 第45列：涨幅Ut
    df.iloc[:, 45] = d                  # 第46列：跌幅Dt
    df.iloc[:, 46] = au                 # 第47列：平均涨幅AUt
    df.iloc[:, 47] = ad                 # 第48列：平均跌幅ADt
    df.iloc[:, 48] = rs                 # 第49列：相对强弱RS
    df.iloc[:, 49] = rsi                # 第50列：RSI
    df.iloc[:, 50] = log_return         # 第51列：对数收益率
    
    # 更新列名
    df.columns.values[24] = '成交量变动率'
    df.columns.values[25] = 'MTM(5)'
    df.columns.values[26] = 'MTM(10)'
    df.columns.values[27] = 'MTM(20)'
    df.columns.values[28] = 'MA(5)'
    df.columns.values[29] = 'MA(10)'
    df.columns.values[30] = 'MA(20)'
    df.columns.values[31] = 'EMA(5)'
    df.columns.values[32] = 'EMA(10)'
    df.columns.values[33] = 'EMA(20)'
    df.columns.values[34] = 'MA(12)'
    df.columns.values[35] = 'MA(26)'
    df.columns.values[36] = 'EMA(12)'
    df.columns.values[37] = 'EMA(26)'
    df.columns.values[38] = 'DIF'
    df.columns.values[39] = 'DIF的9日MA'
    df.columns.values[40] = 'DEA'
    df.columns.values[41] = 'MACD'
    df.columns.values[42] = 'TR'
    df.columns.values[43] = 'ATR'
    df.columns.values[44] = '涨幅Ut'
    df.columns.values[45] = '跌幅Dt'
    df.columns.values[46] = '平均涨幅AUt'
    df.columns.values[47] = '平均跌幅ADt'
    df.columns.values[48] = '相对强弱RS'
    df.columns.values[49] = 'RSI'
    df.columns.values[50] = '对数收益率'
    
    # 保存到原文件
    df.to_excel(file_path, index=False)
    
    print(f"\n所有技术指标计算完成:")
    print(f"成交量变动率 - 有效值: {sum(1 for x in volume_change_rate if not pd.isna(x))}")
    print(f"MTM(5) - 有效值: {sum(1 for x in mtm_5 if not pd.isna(x))}")
    print(f"MTM(10) - 有效值: {sum(1 for x in mtm_10 if not pd.isna(x))}")
    print(f"MTM(20) - 有效值: {sum(1 for x in mtm_20 if not pd.isna(x))}")
    print(f"MA(5) - 有效值: {sum(1 for x in ma_5 if not pd.isna(x))}")
    print(f"MA(10) - 有效值: {sum(1 for x in ma_10 if not pd.isna(x))}")
    print(f"MA(20) - 有效值: {sum(1 for x in ma_20 if not pd.isna(x))}")
    print(f"EMA(5) - 有效值: {sum(1 for x in ema_5 if not pd.isna(x))}")
    print(f"EMA(10) - 有效值: {sum(1 for x in ema_10 if not pd.isna(x))}")
    print(f"EMA(20) - 有效值: {sum(1 for x in ema_20 if not pd.isna(x))}")
    print(f"MA(12) - 有效值: {sum(1 for x in ma_12 if not pd.isna(x))}")
    print(f"MA(26) - 有效值: {sum(1 for x in ma_26 if not pd.isna(x))}")
    print(f"EMA(12) - 有效值: {sum(1 for x in ema_12 if not pd.isna(x))}")
    print(f"EMA(26) - 有效值: {sum(1 for x in ema_26 if not pd.isna(x))}")
    print(f"DIF - 有效值: {sum(1 for x in dif if not pd.isna(x))}")
    print(f"DIF的9日MA - 有效值: {sum(1 for x in dif_ma_9 if not pd.isna(x))}")
    print(f"DEA - 有效值: {sum(1 for x in dea if not pd.isna(x))}")
    print(f"MACD - 有效值: {sum(1 for x in macd if not pd.isna(x))}")
    print(f"TR - 有效值: {sum(1 for x in tr if not pd.isna(x))}")
    print(f"ATR - 有效值: {sum(1 for x in atr if not pd.isna(x))}")
    print(f"涨幅Ut - 有效值: {sum(1 for x in u if not pd.isna(x))}")
    print(f"跌幅Dt - 有效值: {sum(1 for x in d if not pd.isna(x))}")
    print(f"平均涨幅AUt - 有效值: {sum(1 for x in au if not pd.isna(x))}")
    print(f"平均跌幅ADt - 有效值: {sum(1 for x in ad if not pd.isna(x))}")
    print(f"相对强弱RS - 有效值: {sum(1 for x in rs if not pd.isna(x))}")
    print(f"RSI - 有效值: {sum(1 for x in rsi if not pd.isna(x))}")
    print(f"对数收益率 - 有效值: {sum(1 for x in log_return if not pd.isna(x))}")
    
    print(f"\n数据已更新到原文件: {file_path}")
    print(f"更新后数据形状: {df.shape}")
    
    return df

def process_all_files():
    """
    批量处理raw文件夹中的所有xlsx文件
    """
    # 定义文件列表 - 26只股票
    stock_codes = [
        '000002.SZ', '000063.SZ', '000100.SZ', '000157.SZ', '000895.SZ',
        '000001.SZ', '000858.SZ', '002415.SZ', '600036.SH', '600519.SH',
        '600887.SH', '000858.SZ', '002594.SZ', '600276.SH', '000725.SZ',
        '002142.SZ', '600030.SH', '000166.SZ', '002304.SZ', '600585.SH',
        '000776.SZ', '002230.SZ', '600104.SH', '000568.SZ', '002027.SZ',
        '600009.SH'
    ]
    
    # 获取当前脚本所在目录的父目录，然后定位到data/raw文件夹
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    raw_data_dir = os.path.join(parent_dir, 'data', 'raw')
    
    print(f"数据文件夹路径: {raw_data_dir}")
    
    # 检查文件夹是否存在
    if not os.path.exists(raw_data_dir):
        print(f"错误: 数据文件夹不存在: {raw_data_dir}")
        return
    
    processed_files = []
    failed_files = []
    
    # 循环处理每个文件
    for stock_code in stock_codes:
        file_name = f"{stock_code}.xlsx"
        file_path = os.path.join(raw_data_dir, file_name)
        
        print(f"\n{'='*60}")
        print(f"开始处理: {stock_code}")
        print(f"文件路径: {file_path}")
        
        # 检查文件是否存在
        if not os.path.exists(file_path):
            print(f"警告: 文件不存在: {file_path}")
            failed_files.append(stock_code)
            continue
        
        try:
            # 处理文件
            df_updated = calculate_all_indicators(file_path)
            processed_files.append(stock_code)
            print(f"✓ {stock_code} 处理完成")
            
        except Exception as e:
            print(f"✗ {stock_code} 处理失败: {str(e)}")
            failed_files.append(stock_code)
    
    # 输出处理结果汇总
    print(f"\n{'='*60}")
    print("处理结果汇总:")
    print(f"成功处理的文件数量: {len(processed_files)}")
    print(f"成功处理的文件: {processed_files}")
    
    if failed_files:
        print(f"处理失败的文件数量: {len(failed_files)}")
        print(f"处理失败的文件: {failed_files}")
    
    print("\n=== 批量处理完成！ ===")
    print("已为每个文件添加以下指标:")
    print("- 缺失值填充（前向填充优先，后向填充补充）")
    print("- 第25列: 成交量变动率")
    print("- 第26-50列: 各种技术指标（MTM、MA、EMA、MACD、ATR、RSI等）")
    print("- 第51列: 对数收益率")
    
    return processed_files, failed_files

if __name__ == "__main__":
    # 批量处理所有文件
    processed_files, failed_files = process_all_files()