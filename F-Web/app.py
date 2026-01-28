"""
股票数据处理Web应用
提供股票搜索、选择和数据指标处理功能
"""

from flask import Flask, render_template, request, jsonify
import sys
import os

# 添加A-DataBase目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
database_dir = os.path.join(parent_dir, 'A-DataBase')
if database_dir not in sys.path:
    sys.path.insert(0, database_dir)

import pandas as pd
import tushare as ts
import dotenv

# 导入指标计算工具
try:
    from indicator_tools import (
        calculate_mtm_indicators,
        calculate_ma_indicators,
        calculate_ema_indicators,
        calculate_atr_indicators,
        calculate_rsi_indicators,
        calculate_macd_indicators,
        calculate_volume_change_rate
    )
except ImportError as e:
    print(f"警告: 无法导入indicator_tools模块: {e}")
    print(f"当前Python路径: {sys.path}")
    print(f"尝试从以下路径导入: {database_dir}")
    raise
from functools import reduce

app = Flask(__name__)

# 加载环境变量
env_path = os.path.join(parent_dir, '.env')
if os.path.exists(env_path):
    dotenv.load_dotenv(dotenv_path=env_path)
else:
    print(f"警告: .env文件未找到，路径: {env_path}")
API_KEY = os.getenv("TUSHARE_TOKEN")
ts.set_token(API_KEY)
pro = ts.pro_api()

# 数据保存路径
DATA_PATH = os.path.join(os.path.dirname(__file__), 'data')
if not os.path.exists(DATA_PATH):
    os.makedirs(DATA_PATH)

@app.route('/')
def index():
    """首页"""
    return render_template('index.html')

@app.route('/data')
def data_page():
    """数据处理页面"""
    return render_template('data.html')

@app.route('/api/stocks', methods=['GET'])
def get_stocks():
    """获取股票列表"""
    try:
        stock_list = pro.stock_basic(
            exchange='', 
            list_status='L', 
            fields='ts_code,name,area,industry,market'
        )
        stocks = stock_list.to_dict('records')
        return jsonify({
            'success': True,
            'data': stocks
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'获取股票列表失败: {str(e)}'
        }), 500

@app.route('/api/process', methods=['POST'])
def process_data():
    """处理股票数据"""
    try:
        data = request.json
        stock_codes = data.get('stock_codes', [])
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        atr_period = data.get('atr_period', 14)
        rsi_period = data.get('rsi_period', 14)
        
        if not stock_codes:
            return jsonify({
                'success': False,
                'message': '请至少选择一只股票'
            }), 400
        
        if not start_date or not end_date:
            return jsonify({
                'success': False,
                'message': '请选择开始和结束日期'
            }), 400
        
        # 获取股票数据
        data_list = []
        for stock_code in stock_codes:
            try:
                stock_data = pro.daily(
                    ts_code=stock_code,
                    start_date=start_date.replace('-', ''),
                    end_date=end_date.replace('-', ''),
                    fields='ts_code,trade_date,open,high,low,close,pre_close,change,pct_chg,vol,amount'
                )
                
                if stock_data.empty:
                    continue
                
                # 按日期排序（从旧到新）
                stock_data = stock_data.sort_values('trade_date').reset_index(drop=True)
                stock_data.name = stock_code
                data_list.append(stock_data)
            except Exception as e:
                print(f"获取 {stock_code} 数据失败: {str(e)}")
                continue
        
        if not data_list:
            return jsonify({
                'success': False,
                'message': '未能获取任何股票数据，请检查日期范围'
            }), 400
        
        # 计算技术指标
        processed_files = []
        
        for stock_data in data_list:
            # 计算各项指标
            calculate_mtm_indicators(stock_data)
            calculate_ma_indicators(stock_data)
            calculate_ema_indicators(stock_data)
            calculate_atr_indicators(stock_data, n=atr_period)
            calculate_rsi_indicators(stock_data, n=rsi_period)
            calculate_macd_indicators(stock_data)
            calculate_volume_change_rate(stock_data)
            
            # 保存文件
            file_name = f"{stock_data.name}.csv"
            file_path = os.path.join(DATA_PATH, file_name)
            stock_data.to_csv(file_path, index=False)
            processed_files.append(file_name)
        
        # 如果选择了多只股票，生成组合数据
        if len(data_list) > 1:
            def sum_daily_data_reduce(data_list):
                if not data_list:
                    return pd.DataFrame()
                # 先设置trade_date为索引
                for df in data_list:
                    df.set_index('trade_date', inplace=True)
                
                # 对齐并相加（除了ts_code列）
                total = reduce(lambda a, b: a.add(b, fill_value=0), 
                              [df.drop('ts_code', axis=1, errors='ignore') for df in data_list])
                total.reset_index(inplace=True)
                return total
            
            # 重新获取数据用于组合计算
            combo_data_list = []
            for stock_code in stock_codes:
                stock_data = pro.daily(
                    ts_code=stock_code,
                    start_date=start_date.replace('-', ''),
                    end_date=end_date.replace('-', ''),
                    fields='trade_date,open,high,low,close,pre_close,change,pct_chg,vol,amount'
                )
                if not stock_data.empty:
                    stock_data = stock_data.sort_values('trade_date').reset_index(drop=True)
                    combo_data_list.append(stock_data)
            
            daily_total = sum_daily_data_reduce(combo_data_list)
            daily_total.name = 'portfolio_total'
            
            # 计算组合指标
            calculate_mtm_indicators(daily_total)
            calculate_ma_indicators(daily_total)
            calculate_ema_indicators(daily_total)
            calculate_atr_indicators(daily_total, n=atr_period)
            calculate_rsi_indicators(daily_total, n=rsi_period)
            calculate_macd_indicators(daily_total)
            calculate_volume_change_rate(daily_total)
            
            # 保存组合数据
            combo_file = "portfolio_total.csv"
            combo_path = os.path.join(DATA_PATH, combo_file)
            daily_total.to_csv(combo_path, index=False)
            processed_files.append(combo_file)
        
        return jsonify({
            'success': True,
            'message': f'成功处理 {len(data_list)} 只股票的数据',
            'files': processed_files,
            'save_path': DATA_PATH
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'处理失败: {str(e)}'
        }), 500

if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)
