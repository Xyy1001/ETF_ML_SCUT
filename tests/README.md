# 网站交互测试文档

## 概述

本测试套件使用 **Playwright** 和 **pytest** 来测试 ETF-ML 网站的交互功能，特别是模型展示界面的功能。

## 测试内容

### 1. 网站交互测试 (test_website_interaction.py)
- ✅ 导航到模型页面
- ✅ 显示LSTM模型列表
- ✅ 显示GNN模型信息
- ✅ 模型卡片交互（悬停效果）
- ✅ 响应式设计测试（移动端/平板端）
- ✅ 页面截图

### 2. API交互测试 (test_api_interaction.py)
- ✅ 模型概览API测试
- ✅ API响应时间测试
- ✅ 并发请求测试
- ✅ 数据完整性验证

## 环境要求

```bash
# Python依赖
Flask==2.3.3
pandas==2.1.0
numpy==1.24.3
playwright==1.40.0
pytest==7.4.3
pytest-playwright==0.4.3
pytest-html==4.1.1
requests==2.31.0
```

## 本地运行测试

### 1. 安装依赖

```bash
pip install -r requirements.txt
pip install playwright pytest pytest-playwright pytest-html
playwright install chromium
```

### 2. 启动Flask应用

```bash
cd G-Web
python app.py
```

### 3. 运行测试

```bash
# 运行所有测试
pytest tests/ -v

# 运行特定测试文件
pytest tests/test_website_interaction.py -v

# 运行带界面的测试（非无头模式）
pytest tests/ -v --headed

# 生成HTML测试报告
pytest tests/ -v --html=test-results/report.html --self-contained-html
```

## GitHub Actions 自动化测试

### 工作流配置

工作流文件位于：`.github/workflows/github-actions-demo.yml`

### 触发条件

- 推送到 `main` 或 `develop` 分支
- 创建 Pull Request
- 手动触发（workflow_dispatch）

### 工作流步骤

1. **检出代码** - 获取仓库代码
2. **设置Python环境** - 配置Python 3.9/3.10
3. **安装依赖** - 安装Flask和Playwright
4. **创建测试模型** - 生成dummy模型文件用于测试
5. **启动Flask应用** - 后台运行Web服务器
6. **运行测试** - 执行所有测试用例
7. **上传测试结果** - 保存测试报告和截图
8. **停止应用** - 清理进程

### 手动触发测试

在GitHub仓库页面：
1. 点击 "Actions" 标签
2. 选择 "Website Interaction Test" 工作流
3. 点击 "Run workflow" 按钮
4. 选择分支并运行

## 测试架构

```
ETF_ML_SCUT/
├── .github/
│   └── workflows/
│       └── github-actions-demo.yml    # GitHub Actions配置
├── tests/
│   ├── conftest.py                    # Pytest fixtures
│   ├── test_website_interaction.py    # 网站交互测试
│   └── test_api_interaction.py        # API测试
├── pytest.ini                          # Pytest配置
└── test-results/                       # 测试结果输出目录
    └── report.html                     # HTML测试报告
```

## 扩展测试

### 添加新的测试用例

在 `tests/test_website_interaction.py` 中添加新的测试方法：

```python
def test_new_feature(self, page: Page, base_url):
    """测试新功能"""
    page.goto(f"{base_url}/models")
    
    # 你的测试逻辑
    element = page.locator(".your-selector")
    expect(element).to_be_visible()
```

### 测试其他页面

创建新的测试文件，例如 `test_backtest_page.py`：

```python
class TestBacktestPage:
    def test_backtest_form(self, page: Page, base_url):
        """测试回测表单"""
        page.goto(f"{base_url}/backtest")
        # 测试逻辑
```

## 调试技巧

### 1. 使用headed模式查看浏览器操作

```bash
pytest tests/ --headed --slowmo=1000
```

### 2. 查看测试截图

测试失败时会自动截图，保存在 `screenshots/` 目录

### 3. 暂停测试进行调试

```python
page.pause()  # 在代码中添加断点
```

### 4. 查看网络请求

```python
page.on("request", lambda request: print(f">> {request.method} {request.url}"))
page.on("response", lambda response: print(f"<< {response.status} {response.url}"))
```

## 常见问题

### Q: Playwright安装失败？
A: 确保安装浏览器驱动：
```bash
playwright install chromium
```

### Q: 测试超时？
A: 增加超时时间：
```python
page.wait_for_load_state("networkidle", timeout=10000)
```

### Q: 元素找不到？
A: 使用Playwright Inspector调试：
```bash
PWDEBUG=1 pytest tests/test_website_interaction.py
```

## 持续集成最佳实践

1. **保持测试独立** - 每个测试应该独立运行
2. **使用fixtures** - 复用测试设置和清理代码
3. **合理的断言** - 使用Playwright的expect API
4. **截图和报告** - 失败时保存截图便于调试
5. **并行执行** - 使用pytest-xdist加速测试

## 性能监控

在GitHub Actions中，可以查看：
- ⏱️ 测试执行时间
- 📊 测试通过率
- 📈 历史趋势
- 🖼️ 失败截图

## 相关资源

- [Playwright文档](https://playwright.dev/python/)
- [Pytest文档](https://docs.pytest.org/)
- [GitHub Actions文档](https://docs.github.com/actions)
