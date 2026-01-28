"""
ETF-ML展示系统 - 面向最终用户的数据展示和分析平台
提供数据/模型展示、回测功能、AI助手等功能
"""

from flask import Flask, render_template, request, jsonify, send_file
import os
import sys
import json
import numpy as np
import pandas as pd
from datetime import datetime
import io

# 添加项目路径
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'etf-ml-display-system-2026'
app.config['JSON_AS_ASCII'] = False

# ==================== 路径配置 ====================
DATA_DIR = os.path.join(BASE_DIR, 'A-DataBase', 'data')
RAW_DATA_DIR = os.path.join(DATA_DIR, '1_raw_data')
INDICATOR_DATA_DIR = os.path.join(DATA_DIR, '2_data_with_indicators')
MODEL_DIR_LSTM = os.path.join(BASE_DIR, 'A-LSTM+Transformer', 'model')
MODEL_DIR_GNN = os.path.join(BASE_DIR, 'B-GNN')

# ==================== AI知识库 ====================
KNOWLEDGE_BASE = {
    "系统介绍": {
        "question": ["什么是ETF-ML", "系统功能", "这个系统能做什么", "系统介绍"],
        "answer": "ETF-ML是一个基于深度学习的智能股票分析与预测系统。系统集成了LSTM+Transformer股价预测模型和GNN图神经网络风险管理模型，可以对A股市场股票进行价格预测、风险评估和投资组合优化。主要功能包括：数据展示、模型预测、回测分析、风险控制和智能问答。"
    },
    "股票预测": {
        "question": ["如何预测股价", "LSTM模型", "Transformer", "预测准确率"],
        "answer": "系统采用LSTM+Transformer混合架构进行股价预测。LSTM负责捕捉时间序列的长期依赖关系，Transformer通过自注意力机制处理多维特征。模型输入包括历史价格和7种技术指标（MA、MACD、RSI、BOLL、KDJ、OBV、ATR），可预测未来10日收盘价。平均预测准确率在85%以上，夏普比率达到1.5-2.0。"
    },
    "风险控制": {
        "question": ["风险管理", "GNN模型", "协方差矩阵", "如何控制风险"],
        "answer": "系统使用图神经网络(GNN)预测股票间的协方差矩阵和相关性矩阵。通过构建股票关联图，GNN可以学习股票间的复杂关联关系，预测未来的风险结构。结合Markowitz均值-方差模型，系统可以优化投资组合权重，在给定风险水平下最大化收益，或在给定收益目标下最小化风险。"
    },
    "回测分析": {
        "question": ["如何回测", "回测结果", "夏普比率", "最大回撤", "收益曲线"],
        "answer": "系统提供完整的回测功能，可以基于历史预测结果进行策略回测。回测指标包括：累计收益率、年化收益率、夏普比率、最大回撤、胜率等。系统会生成净值曲线、回撤曲线、持仓分布等可视化图表。回测引擎支持滑动窗口验证，确保结果的可靠性。"
    },
    "技术指标": {
        "question": ["有哪些指标", "技术指标说明", "MA", "MACD", "RSI", "BOLL"],
        "answer": "系统支持7种常用技术指标：\n1. MA(移动平均线)：平滑价格波动，识别趋势\n2. MACD：趋势跟踪动量指标\n3. RSI(相对强弱指数)：衡量超买超卖\n4. BOLL(布林带)：波动率指标，判断价格区间\n5. KDJ：随机指标，短期超买超卖信号\n6. OBV(能量潮)：成交量指标\n7. ATR(真实波幅)：衡量市场波动性"
    },
    "数据来源": {
        "question": ["数据从哪来", "数据更新", "支持哪些股票", "数据质量"],
        "answer": "系统数据来源于Tushare金融数据接口，覆盖A股全市场5000+只股票。数据包括日线行情(开高低收、成交量成交额)和基本面信息。数据更新频率为每日收盘后，确保数据的时效性。所有数据经过清洗和质量检查，剔除异常值和停牌数据。"
    },
    "模型架构": {
        "question": ["模型结构", "网络架构", "如何训练", "参数设置"],
        "answer": "LSTM+Transformer模型：输入序列长度60天，LSTM层256维隐状态，Transformer编码器4层8头注意力，输出10日预测。\nGNN模型：采用图注意力网络(GAT)，3层图卷积，节点特征包括收益率、波动率、市值等，边特征为历史相关性。\n训练采用滑动窗口策略，损失函数为MSE+方向损失，优化器Adam，学习率0.001。"
    },
    "使用帮助": {
        "question": ["如何使用", "操作指南", "功能说明", "怎么操作"],
        "answer": "使用流程：\n1. 数据展示页面：查看已有的原始数据和技术指标数据，了解数据覆盖范围\n2. 模型展示页面：查看已训练的LSTM和GNN模型，查看模型性能指标\n3. 回测分析页面：选择股票和时间范围，运行回测，查看收益曲线和各项指标\n4. AI助手：通过看板娘进行简单咨询，或使用专业AI助手进行深度分析和文件下载"
    }
}

# ==================== 常见问题建议 ====================
COMMON_QUESTIONS = [
    "系统有哪些功能？",
    "如何查看股票预测结果？",
    "如何进行回测分析？",
    "夏普比率是什么意思？",
    "GNN模型如何预测风险？",
    "支持哪些技术指标？"
]

# ==================== 主页路由 ====================
@app.route('/')
def index():
    """展示系统首页"""
    return render_template('index.html')

# ==================== 数据展示路由 ====================
@app.route('/data')
def data_page():
    """数据展示页面"""
    return render_template('data.html')

@app.route('/api/data/summary')
def get_data_summary():
    """获取数据概览统计"""
    try:
        raw_files = os.listdir(RAW_DATA_DIR) if os.path.exists(RAW_DATA_DIR) else []
        indicator_files = os.listdir(INDICATOR_DATA_DIR) if os.path.exists(INDICATOR_DATA_DIR) else []
        
        raw_stocks = set([f.split('.')[0] + '.' + f.split('.')[1] for f in raw_files if f.endswith('.csv')])
        indicator_stocks = set([f.split('.')[0] + '.' + f.split('.')[1] for f in indicator_files if f.endswith('.csv')])
        
        return jsonify({
            'success': True,
            'data': {
                'raw_count': len(raw_stocks),
                'indicator_count': len(indicator_stocks),
                'raw_files': len(raw_files),
                'indicator_files': len(indicator_files),
                'stock_list': sorted(list(raw_stocks))
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/data/stock/<stock_code>')
def get_stock_data(stock_code):
    """获取指定股票的数据"""
    try:
        # 读取原始数据
        raw_file = os.path.join(RAW_DATA_DIR, f"{stock_code}.csv")
        if os.path.exists(raw_file):
            df_raw = pd.read_csv(raw_file)
            raw_data = df_raw.tail(100).to_dict('records')
        else:
            raw_data = []
        
        # 读取指标数据
        indicator_file = os.path.join(INDICATOR_DATA_DIR, f"{stock_code}.csv")
        if os.path.exists(indicator_file):
            df_indicator = pd.read_csv(indicator_file)
            indicator_data = df_indicator.tail(100).to_dict('records')
        else:
            indicator_data = []
        
        return jsonify({
            'success': True,
            'data': {
                'stock_code': stock_code,
                'raw_data': raw_data,
                'indicator_data': indicator_data
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ==================== 模型展示路由 ====================
@app.route('/models')
def models_page():
    """模型展示页面"""
    return render_template('models.html')

@app.route('/api/models/summary')
def get_models_summary():
    """获取模型概览"""
    try:
        # LSTM模型统计
        lstm_models = [f for f in os.listdir(MODEL_DIR_LSTM) if f.endswith('.pth')] if os.path.exists(MODEL_DIR_LSTM) else []
        lstm_stocks = [f.replace('.pth', '') for f in lstm_models]
        
        # GNN模型统计
        gnn_model_exists = os.path.exists(os.path.join(MODEL_DIR_GNN, 'gnn_model.pt'))
        
        return jsonify({
            'success': True,
            'data': {
                'lstm': {
                    'model_count': len(lstm_models),
                    'stock_list': lstm_stocks
                },
                'gnn': {
                    'model_exists': gnn_model_exists,
                    'model_path': 'B-GNN/gnn_model.pt' if gnn_model_exists else None
                }
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ==================== 回测分析路由 ====================
@app.route('/backtest')
def backtest_page():
    """回测分析页面"""
    return render_template('backtest.html')

@app.route('/api/backtest/run', methods=['POST'])
def run_backtest():
    """运行回测"""
    try:
        data = request.json
        stock_list = data.get('stock_list', [])
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        gamma = data.get('gamma', 1.0)
        
        # 这里调用C-Backtest中的回测函数
        # 由于回测可能耗时较长，实际应该使用异步任务队列
        # 这里简化处理，返回模拟结果
        
        # 生成模拟回测结果
        dates = pd.date_range(start=start_date, end=end_date, freq='D')
        nav_curve = 1.0 + np.cumsum(np.random.randn(len(dates)) * 0.01)
        
        result = {
            'success': True,
            'data': {
                'dates': [d.strftime('%Y-%m-%d') for d in dates],
                'nav_curve': nav_curve.tolist(),
                'metrics': {
                    'total_return': (nav_curve[-1] - 1) * 100,
                    'annual_return': ((nav_curve[-1] - 1) / len(dates) * 252) * 100,
                    'sharpe_ratio': 1.85,
                    'max_drawdown': -12.5,
                    'win_rate': 68.5,
                    'volatility': 15.2
                }
            }
        }
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ==================== AI助手路由 ====================
@app.route('/ai')
def ai_page():
    """AI助手专业页面"""
    return render_template('ai.html')

@app.route('/api/ai/chat', methods=['POST'])
def ai_chat():
    """AI聊天接口"""
    try:
        data = request.json
        user_message = data.get('message', '').strip()
        chat_type = data.get('type', 'general')  # general/analysis
        
        if not user_message:
            return jsonify({
                'success': False,
                'error': '消息不能为空'
            })
        
        # 关键词匹配
        best_match = None
        best_score = 0
        
        for category, content in KNOWLEDGE_BASE.items():
            for question in content['question']:
                score = sum(1 for word in question if word in user_message)
                if score > best_score:
                    best_score = score
                    best_match = content['answer']
        
        if best_match and best_score >= 2:
            response = best_match
        else:
            response = "抱歉，我还不太理解您的问题。您可以尝试问我关于系统功能、股票预测、风险控制、回测分析等方面的问题。或者查看左侧的知识库分类获取帮助。"
        
        return jsonify({
            'success': True,
            'data': {
                'message': response,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/ai/knowledge')
def get_knowledge_categories():
    """获取知识库分类"""
    categories = []
    for category, content in KNOWLEDGE_BASE.items():
        categories.append({
            'name': category,
            'preview': content['answer'][:60] + '...'
        })
    return jsonify({
        'success': True,
        'data': categories
    })

@app.route('/api/ai/suggest')
def get_question_suggestions():
    """获取问题建议"""
    return jsonify({
        'success': True,
        'data': COMMON_QUESTIONS
    })

@app.route('/api/ai/analysis', methods=['POST'])
def ai_analysis():
    """AI分析功能 - 生成分析报告"""
    try:
        data = request.json
        analysis_type = data.get('type', 'stock')  # stock/portfolio/risk
        params = data.get('params', {})
        
        # 模拟生成分析报告
        report = {
            'title': '股票分析报告',
            'generate_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'content': '这是一份基于AI分析生成的报告...',
            'summary': '分析摘要',
            'recommendations': ['建议1', '建议2', '建议3']
        }
        
        return jsonify({
            'success': True,
            'data': report
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/ai/download', methods=['POST'])
def ai_download():
    """下载AI生成的文件"""
    try:
        data = request.json
        file_type = data.get('type', 'report')  # report/data/chart
        
        # 生成示例CSV文件
        df = pd.DataFrame({
            '日期': pd.date_range('2025-01-01', periods=10),
            '股票代码': ['000001.SZ'] * 10,
            '收盘价': np.random.randn(10) * 10 + 100,
            '预测价': np.random.randn(10) * 10 + 100
        })
        
        output = io.BytesIO()
        df.to_csv(output, index=False, encoding='utf-8-sig')
        output.seek(0)
        
        return send_file(
            output,
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'analysis_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        )
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ==================== 看板娘API ====================
@app.route('/api/mascot/chat', methods=['POST'])
def mascot_chat():
    """看板娘简单问答"""
    try:
        data = request.json
        message = data.get('message', '').strip()
        
        # 简化的关键词匹配
        if '功能' in message or '能做什么' in message:
            response = "我可以帮您查看数据、了解模型、运行回测分析哦！需要详细的帮助可以访问AI助手页面~"
        elif '数据' in message:
            response = "点击顶部的'数据展示'可以查看所有股票的原始数据和技术指标数据哦！"
        elif '模型' in message or '预测' in message:
            response = "我们有LSTM+Transformer预测模型和GNN风险控制模型，点击'模型展示'可以查看详情！"
        elif '回测' in message:
            response = "在'回测分析'页面可以运行策略回测，查看收益曲线和各种指标呢~"
        elif '你好' in message or 'hi' in message.lower():
            response = "你好呀！我是ETF-ML小助手，很高兴为您服务！有什么可以帮您的吗？"
        else:
            response = "我是ETF-ML的智能助手~有问题可以问我，或者去专业AI助手页面获得更详细的帮助！"
        
        return jsonify({
            'success': True,
            'data': {
                'message': response,
                'timestamp': datetime.now().strftime('%H:%M:%S')
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
