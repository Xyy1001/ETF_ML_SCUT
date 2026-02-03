"""
网站交互测试 - 使用Playwright进行端到端测试
测试模型展示页面的交互功能
"""

import pytest
from playwright.sync_api import Page, expect
import os
import time


@pytest.fixture(scope="session")
def base_url():
    """基础URL配置"""
    return os.getenv("BASE_URL", "http://localhost:5000")


class TestModelPageInteraction:
    """测试模型展示页面的交互"""
    
    def test_navigate_to_models_page(self, page: Page, base_url):
        """测试导航到模型页面"""
        # 访问首页
        page.goto(base_url)
        
        # 等待页面加载
        page.wait_for_load_state("networkidle")
        
        # 点击"模型展示"导航链接
        models_link = page.get_by_text("模型展示")
        expect(models_link).to_be_visible()
        models_link.click()
        
        # 验证URL已改变
        expect(page).to_have_url(f"{base_url}/models")
        
        # 验证页面标题
        expect(page).to_have_title("模型展示 | ETF-ML")
    
    def test_display_lstm_models(self, page: Page, base_url):
        """测试LSTM模型展示"""
        # 导航到模型页面
        page.goto(f"{base_url}/models")
        page.wait_for_load_state("networkidle")
        
        # 等待模型数据加载
        page.wait_for_timeout(1000)
        
        # 验证LSTM模型卡片存在
        lstm_card = page.locator(".model-card:has-text('LSTM+Transformer')")
        expect(lstm_card).to_be_visible()
        
        # 验证模型计数显示
        model_count = page.locator(".stat-value").first
        expect(model_count).to_be_visible()
        
    def test_display_gnn_model(self, page: Page, base_url):
        """测试GNN模型展示"""
        page.goto(f"{base_url}/models")
        page.wait_for_load_state("networkidle")
        
        # 等待模型数据加载
        page.wait_for_timeout(1000)
        
        # 验证GNN模型卡片存在
        gnn_card = page.locator(".model-card:has-text('GNN')")
        expect(gnn_card).to_be_visible()
    
    def test_model_list_display(self, page: Page, base_url):
        """测试模型列表展示"""
        page.goto(f"{base_url}/models")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1500)
        
        # 验证模型列表容器存在
        model_list = page.locator(".model-list").first
        expect(model_list).to_be_visible()
        
        # 验证至少有一个模型项
        model_items = page.locator(".model-item")
        expect(model_items.first).to_be_visible(timeout=5000)
    
    def test_api_models_summary(self, page: Page, base_url):
        """测试模型概览API"""
        # 直接访问API端点
        response = page.goto(f"{base_url}/api/models/summary")
        
        # 验证响应状态
        assert response.status == 200
        
        # 解析JSON响应
        data = response.json()
        assert data['success'] is True
        assert 'lstm' in data['data']
        assert 'gnn' in data['data']
        
    def test_screenshot_models_page(self, page: Page, base_url):
        """截图模型页面（用于调试）"""
        page.goto(f"{base_url}/models")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)
        
        # 创建截图目录
        os.makedirs("screenshots", exist_ok=True)
        
        # 截图
        page.screenshot(path="screenshots/models_page.png", full_page=True)


class TestModelInteraction:
    """测试模型交互功能"""
    
    def test_hover_model_card(self, page: Page, base_url):
        """测试鼠标悬停模型卡片效果"""
        page.goto(f"{base_url}/models")
        page.wait_for_load_state("networkidle")
        
        # 找到第一个模型卡片
        model_card = page.locator(".model-card").first
        expect(model_card).to_be_visible()
        
        # 悬停操作
        model_card.hover()
        
        # 等待动画效果
        page.wait_for_timeout(500)
        
        # 验证悬停样式（这里可以验证transform或其他CSS属性）
        # 注意：Playwright可以检查计算后的样式
    
    def test_model_card_content(self, page: Page, base_url):
        """测试模型卡片内容完整性"""
        page.goto(f"{base_url}/models")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1000)
        
        # 验证关键元素
        expect(page.locator(".model-icon").first).to_be_visible()
        expect(page.locator(".model-title").first).to_be_visible()
        expect(page.locator(".model-desc").first).to_be_visible()
        expect(page.locator(".model-stats").first).to_be_visible()


class TestResponsiveness:
    """测试响应式设计"""
    
    def test_mobile_view(self, page: Page, base_url):
        """测试移动端视图"""
        # 设置移动设备视口
        page.set_viewport_size({"width": 375, "height": 667})
        
        page.goto(f"{base_url}/models")
        page.wait_for_load_state("networkidle")
        
        # 验证布局适配
        model_grid = page.locator(".model-grid")
        expect(model_grid).to_be_visible()
        
        # 截图
        os.makedirs("screenshots", exist_ok=True)
        page.screenshot(path="screenshots/models_page_mobile.png")
    
    def test_tablet_view(self, page: Page, base_url):
        """测试平板端视图"""
        # 设置平板设备视口
        page.set_viewport_size({"width": 768, "height": 1024})
        
        page.goto(f"{base_url}/models")
        page.wait_for_load_state("networkidle")
        
        # 验证布局
        model_grid = page.locator(".model-grid")
        expect(model_grid).to_be_visible()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--headed"])
