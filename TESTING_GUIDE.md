# GitHub Actions 网站交互测试 - 快速入门

## 🎯 目标

自动化测试网站交互功能，特别是点击"模型展示"按钮后显示项目中的模型列表。

## 📦 已创建的文件

```
ETF_ML_SCUT/
├── .github/workflows/
│   └── github-actions-demo.yml          # GitHub Actions工作流配置
├── tests/
│   ├── conftest.py                      # Pytest配置和fixtures
│   ├── test_website_interaction.py      # 网站UI交互测试
│   ├── test_api_interaction.py          # API接口测试
│   ├── run_tests.py                     # 本地快速测试脚本
│   └── README.md                        # 详细文档
├── pytest.ini                           # Pytest配置
└── requirements-test.txt                # 测试依赖
```

## 🚀 本地快速测试（3步）

### 1️⃣ 安装依赖

```bash
cd ETF_ML_SCUT
pip install -r requirements-test.txt
playwright install chromium
```

### 2️⃣ 运行测试脚本

```bash
python tests/run_tests.py
```

或者手动方式：

```bash
# 终端1：启动Flask
cd G-Web
python app.py

# 终端2：运行测试
cd ETF_ML_SCUT
pytest tests/ -v --html=test-results/report.html
```

### 3️⃣ 查看结果

测试报告位于：`test-results/report.html`

## ☁️ GitHub Actions 自动化测试

### 设置步骤

1. **提交代码到GitHub**
   ```bash
   git add .github/workflows/github-actions-demo.yml
   git add tests/
   git add pytest.ini requirements-test.txt
   git commit -m "添加GitHub Actions网站交互测试"
   git push
   ```

2. **查看运行结果**
   - 访问GitHub仓库
   - 点击 "Actions" 标签
   - 查看 "Website Interaction Test" 工作流

3. **手动触发测试**
   - 在Actions页面点击工作流名称
   - 点击 "Run workflow" 按钮
   - 选择分支并运行

### 自动触发条件

- ✅ 推送代码到 `main` 或 `develop` 分支
- ✅ 创建或更新 Pull Request
- ✅ 手动触发

## 🧪 测试覆盖内容

### ✨ 网站交互测试
- ✅ 点击导航到模型页面
- ✅ 验证页面标题和URL
- ✅ 显示LSTM模型卡片
- ✅ 显示GNN模型卡片
- ✅ 显示模型列表（项目中的实际模型）
- ✅ 模型卡片悬停效果
- ✅ 响应式设计（移动端/平板端）

### 🔌 API测试
- ✅ `/api/models/summary` - 获取模型概览
- ✅ 验证返回数据结构
- ✅ 测试响应时间
- ✅ 并发请求测试
- ✅ 数据完整性验证

## 📊 测试示例

### 示例1：测试模型列表显示

```python
def test_display_lstm_models(page, base_url):
    # 访问模型页面
    page.goto(f"{base_url}/models")
    
    # 验证LSTM模型卡片存在
    lstm_card = page.locator(".model-card:has-text('LSTM+Transformer')")
    expect(lstm_card).to_be_visible()
    
    # 验证模型列表
    model_list = page.locator(".model-list")
    expect(model_list).to_be_visible()
```

### 示例2：测试API返回的模型数据

```python
def test_api_models_summary(page, base_url):
    response = page.goto(f"{base_url}/api/models/summary")
    data = response.json()
    
    # 验证响应结构
    assert data['success'] is True
    assert 'lstm' in data['data']
    assert 'gnn' in data['data']
    
    # 验证LSTM模型列表
    stock_list = data['data']['lstm']['stock_list']
    assert len(stock_list) > 0  # 至少有一个模型
```

## 🎨 自定义测试

### 添加新测试用例

在 `tests/test_website_interaction.py` 添加：

```python
def test_your_feature(self, page: Page, base_url):
    """测试你的新功能"""
    page.goto(f"{base_url}/your-page")
    
    # 点击按钮
    button = page.locator("#your-button")
    button.click()
    
    # 验证结果
    result = page.locator(".result")
    expect(result).to_have_text("期望的文本")
```

### 测试其他交互

```python
# 测试表单提交
page.fill("#input-field", "test value")
page.click("#submit-button")

# 测试下拉选择
page.select_option("#dropdown", "option-value")

# 测试文件上传
page.set_input_files("#file-input", "path/to/file")

# 测试拖拽
page.drag_and_drop("#source", "#target")
```

## 🐛 调试技巧

### 查看浏览器操作

```bash
pytest tests/ --headed --slowmo=1000
```

### 使用调试器

```python
page.pause()  # 代码中添加断点
```

### 运行单个测试

```bash
pytest tests/test_website_interaction.py::TestModelPageInteraction::test_navigate_to_models_page -v
```

### 查看详细日志

```bash
pytest tests/ -v -s --log-cli-level=DEBUG
```

## 📈 持续改进

### 添加性能测试

```python
def test_page_load_time(page, base_url):
    import time
    start = time.time()
    page.goto(f"{base_url}/models")
    load_time = time.time() - start
    assert load_time < 3.0, f"页面加载过慢: {load_time}s"
```

### 添加截图比对

```python
def test_visual_regression(page, base_url):
    page.goto(f"{base_url}/models")
    page.screenshot(path="screenshots/baseline.png")
    # 可以使用工具比对截图差异
```

## 🔗 相关链接

- [GitHub Actions配置](.github/workflows/github-actions-demo.yml)
- [详细测试文档](tests/README.md)
- [Playwright文档](https://playwright.dev/python/)

## ❓ 常见问题

**Q: 本地测试通过，但GitHub Actions失败？**
A: 检查环境差异，确保依赖版本一致，可能需要调整等待时间。

**Q: 如何测试需要登录的页面？**
A: 在conftest.py中添加登录fixture：
```python
@pytest.fixture
def logged_in_page(page, base_url):
    page.goto(f"{base_url}/login")
    page.fill("#username", "test")
    page.fill("#password", "test")
    page.click("#login-button")
    return page
```

**Q: 测试太慢怎么办？**
A: 使用并行测试：
```bash
pytest tests/ -n auto  # 自动使用所有CPU核心
```

## 🎉 完成！

现在你已经有了完整的网站交互测试系统：
- ✅ 本地开发测试
- ✅ GitHub Actions自动化
- ✅ 详细的测试报告
- ✅ 截图和调试工具

开始测试你的网站交互吧！🚀
