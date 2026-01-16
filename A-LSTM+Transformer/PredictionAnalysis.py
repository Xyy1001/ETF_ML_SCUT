from ast import main
import pandas as pd
import os
import dotenv
import numpy as np

loaded = dotenv.load_dotenv(dotenv_path="Transformer+LSTM/Advanced/.env")
API_KEY = os.getenv("TUSHARE_TOKEN")
print(API_KEY)

# 初始化接口
import tushare as ts
ts.set_token(API_KEY)
pro = ts.pro_api()

# 设置数据分割时间
start_date = os.getenv("start_date")
end_date = os.getenv("end_date")

# 读取文件夹中各股股票未来20天的预测结果
def read_future_predictions(folder_path):
    predictions = {}
    for file_name in os.listdir(folder_path):
        if file_name.endswith(".csv"):
            # 期望文件名格式为 predictions_{ts_code}.csv，例如 predictions_000001.SZ.csv
            parts = file_name.split("_", 1)
            if len(parts) > 1:
                stock_name = parts[1]
            else:
                stock_name = parts[0]
            # 去掉 .csv 后缀（如果存在）
            stock_name = stock_name.replace('.csv', '')
            df = pd.read_csv(os.path.join(folder_path, file_name))
            if len(df) >= 20:
                predictions[stock_name] = df['pred_close'].values
            else:
                print(f"文件 {file_name} 中的数据不足20天，已跳过。")
    return predictions

# 分析获取未来20天内预测值的各项分析指标
def analyze_predictions(predictions):
    analysis_results = {}
    for stock, preds in predictions.items():
        max_pred = max(preds)
        min_pred = min(preds)
        avg_pred = sum(preds) / len(preds)
        analysis_results[stock] = {
            'max': max_pred,
            'min': min_pred,
            'average': avg_pred
        }
    return analysis_results

# 对多股股票的综合预测结果进行收益权重分析
# 就是用未来预测20天的均值作为收益预测，然后计算各股的收益向量
def weighted_analysis(analysis_results):
    avg_weights = {}
    max_weights = {}
    min_weights = {}
    skipped = []

    for stock, metrics in analysis_results.items():
        # 获取基准收盘价（尝试按 end_date 查询，若无则降级到区间查询）
        try:
            df_price = pro.daily(ts_code=stock, trade_date=end_date)
        except Exception as e:
            print(f"调用 tushare 获取 {stock} 在 {end_date} 的 daily 失败: {e}")
            df_price = None

        if df_price is None or df_price.empty:
            try:
                df_price = pro.daily(ts_code=stock, start_date=start_date, end_date=end_date)
            except Exception as e:
                print(f"降级查询 tushare 失败: {e}")
                df_price = None

        if df_price is None or df_price.empty:
            print(f"跳过 {stock}：未找到 {end_date} 或之前的交易数据")
            skipped.append(stock)
            continue

        # 取最近交易日的 close
        if 'trade_date' in df_price.columns:
            df_price = df_price.sort_values('trade_date')
        real_final_price = float(df_price.iloc[-1]['close'])
        if real_final_price == 0 or np.isnan(real_final_price):
            print(f"跳过 {stock}：基准价格无效 -> {real_final_price}")
            skipped.append(stock)
            continue

        # 计算三类预测回报并记录
        avg_weights[stock] = (metrics['average'] - real_final_price) / real_final_price
        max_weights[stock] = (metrics['max'] - real_final_price) / real_final_price
        min_weights[stock] = (metrics['min'] - real_final_price) / real_final_price

    if skipped:
        print(f"已跳过以下股票（无有效基准价）：{skipped}")

    return avg_weights, max_weights, min_weights

if __name__ == "__main__":
    folder_path = input("请输入包含未来预测结果的文件夹路径: ")
    predictions = read_future_predictions(folder_path)
    analysis_results = analyze_predictions(predictions)
    avg_weights, max_weights, min_weights = weighted_analysis(analysis_results)
    print("基于平均预测的收益权重:", avg_weights)
    print("基于最大预测的收益权重:", max_weights)
    print("基于最小预测的收益权重:", min_weights)