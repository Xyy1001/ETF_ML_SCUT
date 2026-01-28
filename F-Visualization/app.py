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
DATA_PATH = os.path.join('A-DataBase/data/1_raw_data')
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

@app.route('/train')
def train_page():
    """模型训练页面"""
    return render_template('train.html')

@app.route('/risk')
def risk_page():
    """风险管理页面"""
    return render_template('risk.html')

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
        
        """
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
            """
        
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

# ==================== 模型训练相关API ====================

@app.route('/api/models', methods=['GET'])
def get_models():
    """获取已训练的模型列表"""
    try:
        model_dir = os.path.join(parent_dir, 'A-LSTM+Transformer', 'model')
        if not os.path.exists(model_dir):
            return jsonify({
                'success': True,
                'data': []
            })
        
        models = []
        for file in os.listdir(model_dir):
            if file.endswith('.pth'):
                file_path = os.path.join(model_dir, file)
                file_stat = os.stat(file_path)
                models.append({
                    'name': file,
                    'stock_code': file.replace('.pth', ''),
                    'size': f"{file_stat.st_size / 1024:.2f} KB",
                    'modified': pd.Timestamp.fromtimestamp(file_stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                })
        
        return jsonify({
            'success': True,
            'data': sorted(models, key=lambda x: x['modified'], reverse=True)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'获取模型列表失败: {str(e)}'
        }), 500

@app.route('/api/training-data', methods=['GET'])
def get_training_data():
    """获取可用的训练数据列表"""
    try:
        data_dir = os.path.join(parent_dir, 'A-DataBase', 'data', '1_raw_data')
        if not os.path.exists(data_dir):
            return jsonify({
                'success': True,
                'data': []
            })
        
        data_files = []
        for file in os.listdir(data_dir):
            if file.endswith('.csv'):
                file_path = os.path.join(data_dir, file)
                file_stat = os.stat(file_path)
                
                # 读取CSV文件获取行数
                try:
                    df = pd.read_csv(file_path)
                    rows = len(df)
                    cols = len(df.columns)
                except:
                    rows = 0
                    cols = 0
                
                data_files.append({
                    'name': file,
                    'stock_code': file.replace('.csv', ''),
                    'size': f"{file_stat.st_size / 1024:.2f} KB",
                    'rows': rows,
                    'columns': cols,
                    'modified': pd.Timestamp.fromtimestamp(file_stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                })
        
        return jsonify({
            'success': True,
            'data': sorted(data_files, key=lambda x: x['modified'], reverse=True)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'获取数据列表失败: {str(e)}'
        }), 500

@app.route('/api/train', methods=['POST'])
def start_training():
    """开始模型训练"""
    try:
        data = request.json
        data_file = data.get('data_file')
        epochs = data.get('epochs', 100)
        batch_size = data.get('batch_size', 32)
        learning_rate = data.get('learning_rate', 0.001)
        input_window = data.get('input_window', 100)
        output_window = data.get('output_window', 10)
        lstm_hidden = data.get('lstm_hidden', 64)
        
        if not data_file:
            return jsonify({
                'success': False,
                'message': '请选择训练数据文件'
            }), 400
        
        # 验证数据文件是否存在
        data_path = os.path.join(parent_dir, 'A-DataBase', 'data', '1_raw_data', data_file)
        if not os.path.exists(data_path):
            return jsonify({
                'success': False,
                'message': '数据文件不存在'
            }), 400
        
        # 这里应该启动一个后台训练任务
        # 由于Flask默认是同步的，这里先返回一个简单的响应
        # 实际应用中应该使用Celery或multiprocessing来处理
        
        return jsonify({
            'success': True,
            'message': '训练任务已提交',
            'training_id': f"train_{data_file}_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}",
            'config': {
                'data_file': data_file,
                'epochs': epochs,
                'batch_size': batch_size,
                'learning_rate': learning_rate,
                'input_window': input_window,
                'output_window': output_window,
                'lstm_hidden': lstm_hidden
            }
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'训练失败: {str(e)}'
        }), 500

# ==================== 风险管理相关API ====================

@app.route('/api/risk-methods', methods=['GET'])
def get_risk_methods():
    """获取可用的风险管理方法"""
    methods = [
        {
            'id': 'covariance',
            'name': '协方差矩阵预测',
            'description': '基于GNN预测股票收益率的协方差矩阵，用于投资组合优化',
            'module': 'src',
            'icon': 'grid'
        },
        {
            'id': 'correlation',
            'name': '相关系数矩阵预测',
            'description': '基于GNN预测股票收益率的相关系数矩阵，用于风险管理',
            'module': 'coefficient',
            'icon': 'link'
        }
    ]
    return jsonify({
        'success': True,
        'data': methods
    })

@app.route('/api/risk-models', methods=['GET'])
def get_risk_models():
    """获取已训练的风险模型列表"""
    try:
        gnn_dir = os.path.join(parent_dir, 'B-GNN')
        models = []
        
        # 检查主目录下的模型文件
        if os.path.exists(gnn_dir):
            for file in os.listdir(gnn_dir):
                if file.endswith('.pt') or file.endswith('.pth'):
                    file_path = os.path.join(gnn_dir, file)
                    file_stat = os.stat(file_path)
                    models.append({
                        'name': file,
                        'method': 'GNN风险模型',
                        'size': f"{file_stat.st_size / 1024:.2f} KB",
                        'modified': pd.Timestamp.fromtimestamp(file_stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                    })
        
        return jsonify({
            'success': True,
            'data': sorted(models, key=lambda x: x['modified'], reverse=True)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'获取模型列表失败: {str(e)}'
        }), 500

@app.route('/api/risk-data', methods=['GET'])
def get_risk_training_data():
    """获取可用的风险训练数据"""
    try:
        data_dirs = [
            ('B-GNN/1', '预处理数据集1'),
            ('B-GNN/raw', '原始数据')
        ]
        
        data_files = []
        for rel_path, desc in data_dirs:
            data_dir = os.path.join(parent_dir, rel_path)
            if os.path.exists(data_dir):
                for file in os.listdir(data_dir):
                    if file.endswith('.npy') or file.endswith('.xlsx'):
                        file_path = os.path.join(data_dir, file)
                        file_stat = os.stat(file_path)
                        data_files.append({
                            'name': file,
                            'path': rel_path,
                            'description': desc,
                            'size': f"{file_stat.st_size / 1024:.2f} KB",
                            'modified': pd.Timestamp.fromtimestamp(file_stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                        })
        
        return jsonify({
            'success': True,
            'data': sorted(data_files, key=lambda x: x['modified'], reverse=True)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'获取数据列表失败: {str(e)}'
        }), 500

@app.route('/api/risk-train', methods=['POST'])
def start_risk_training():
    """开始风险模型训练"""
    try:
        data = request.json
        method = data.get('method')  # 'covariance' or 'correlation'
        epochs = data.get('epochs', 100)
        batch_size = data.get('batch_size', 32)
        learning_rate = data.get('learning_rate', 0.001)
        lookback = data.get('lookback', 100)
        horizon = data.get('horizon', 10)
        
        if not method:
            return jsonify({
                'success': False,
                'message': '请选择风险管理方法'
            }), 400
        
        # 验证方法类型
        valid_methods = ['covariance', 'correlation']
        if method not in valid_methods:
            return jsonify({
                'success': False,
                'message': f'无效的方法类型，必须是: {", ".join(valid_methods)}'
            }), 400
        
        # 确定使用的模块目录
        module_dir = 'src' if method == 'covariance' else 'coefficient'
        
        # 这里应该启动后台训练任务
        # 实际应用中应该使用Celery或multiprocessing
        
        return jsonify({
            'success': True,
            'message': '风险模型训练任务已提交',
            'training_id': f"risk_{method}_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}",
            'config': {
                'method': method,
                'module': module_dir,
                'epochs': epochs,
                'batch_size': batch_size,
                'learning_rate': learning_rate,
                'lookback': lookback,
                'horizon': horizon
            }
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'训练失败: {str(e)}'
        }), 500

if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)
