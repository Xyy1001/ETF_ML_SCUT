"""
API交互测试 - 测试模型相关的API端点
"""

import pytest
import requests
import json


@pytest.fixture(scope="module")
def api_base_url():
    """API基础URL"""
    return "http://localhost:5000/api"


class TestModelsAPI:
    """测试模型相关API"""
    
    def test_get_models_summary_success(self, api_base_url):
        """测试获取模型概览 - 成功场景"""
        response = requests.get(f"{api_base_url}/models/summary")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data['success'] is True
        assert 'data' in data
        assert 'lstm' in data['data']
        assert 'gnn' in data['data']
        
        # 验证LSTM数据结构
        lstm_data = data['data']['lstm']
        assert 'model_count' in lstm_data
        assert 'stock_list' in lstm_data
        assert isinstance(lstm_data['model_count'], int)
        assert isinstance(lstm_data['stock_list'], list)
        
        # 验证GNN数据结构
        gnn_data = data['data']['gnn']
        assert 'model_exists' in gnn_data
        assert isinstance(gnn_data['model_exists'], bool)
    
    def test_models_summary_response_time(self, api_base_url):
        """测试API响应时间"""
        import time
        start = time.time()
        response = requests.get(f"{api_base_url}/models/summary")
        end = time.time()
        
        response_time = end - start
        
        # 验证响应时间小于1秒
        assert response_time < 1.0, f"API响应时间过长: {response_time}s"
        assert response.status_code == 200
    
    def test_models_summary_content_type(self, api_base_url):
        """测试响应内容类型"""
        response = requests.get(f"{api_base_url}/models/summary")
        
        assert response.status_code == 200
        assert 'application/json' in response.headers['Content-Type']
    
    def test_concurrent_requests(self, api_base_url):
        """测试并发请求"""
        import concurrent.futures
        
        def make_request():
            response = requests.get(f"{api_base_url}/models/summary")
            return response.status_code == 200
        
        # 创建10个并发请求
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request) for _ in range(10)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
        
        # 所有请求都应该成功
        assert all(results), "某些并发请求失败"


class TestBacktestAPI:
    """测试回测API"""
    
    def test_backtest_run_endpoint_exists(self, api_base_url):
        """测试回测端点存在"""
        # POST请求需要数据
        test_data = {
            "stock_list": ["600519", "000001"],
            "start_date": "2023-01-01",
            "end_date": "2023-12-31",
            "gamma": 1.0
        }
        
        response = requests.post(
            f"{api_base_url}/backtest/run",
            json=test_data,
            headers={'Content-Type': 'application/json'}
        )
        
        # 验证端点可访问（可能返回200或其他有效状态码）
        assert response.status_code in [200, 400, 500]  # 端点存在


class TestModelDataIntegrity:
    """测试模型数据完整性"""
    
    def test_lstm_models_data_structure(self, api_base_url):
        """验证LSTM模型数据结构"""
        response = requests.get(f"{api_base_url}/models/summary")
        data = response.json()
        
        lstm_data = data['data']['lstm']
        stock_list = lstm_data['stock_list']
        
        # 验证股票代码格式
        for stock in stock_list:
            assert isinstance(stock, str), f"股票代码应为字符串: {stock}"
            # 中国股票代码应为6位数字
            if stock.isdigit():
                assert len(stock) == 6, f"股票代码长度错误: {stock}"
    
    def test_model_count_consistency(self, api_base_url):
        """验证模型数量与列表一致性"""
        response = requests.get(f"{api_base_url}/models/summary")
        data = response.json()
        
        lstm_data = data['data']['lstm']
        model_count = lstm_data['model_count']
        stock_list = lstm_data['stock_list']
        
        # 模型数量应该等于股票列表长度
        assert model_count == len(stock_list), \
            f"模型数量({model_count})与股票列表长度({len(stock_list)})不一致"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
