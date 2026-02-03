# ETF-ML 静态网站

## 概述
基于深度学习的智能股票预测与分析平台的静态网站展示。

## 文件结构
```
ETF_ML_SCUT/
├── index.html          # 首页
├── data.html          # 数据展示页
├── models.html        # 模型展示页
├── backtest.html      # 回测分析页
├── ai.html            # AI助手页
├── static/            # 静态资源目录
│   ├── style.css      # 全局样式
│   ├── ai.css         # AI页面样式
│   ├── data.css       # 数据页面样式
│   ├── mascot.css     # 看板娘样式
│   ├── index.js       # 首页脚本
│   ├── data.js        # 数据页面脚本
│   ├── ai.js          # AI页面脚本
│   └── mascot.js      # 看板娘脚本
└── README.md          # 本文档
```

## 使用方法

### 方法1: 直接在浏览器中打开
1. 双击 `index.html` 文件，浏览器会自动打开首页
2. 通过导航栏访问其他页面

### 方法2: 使用本地服务器（推荐）
使用Python内置的HTTP服务器：

```bash
# 进入项目目录
cd e:\Machine_Learning_ETF\ETF_ML_SCUT

# 启动服务器（Python 3）
python -m http.server 8000

# 或者使用Python 2
python -m SimpleHTTPServer 8000
```

然后在浏览器中访问：http://localhost:8000

### 方法3: 使用VS Code Live Server
1. 在VS Code中安装 "Live Server" 插件
2. 右键点击 `index.html`
3. 选择 "Open with Live Server"

## 功能页面

- **首页 (index.html)**: 系统介绍、功能概览、技术架构展示
- **数据展示 (data.html)**: 原始股票数据和技术指标数据查看
- **模型展示 (models.html)**: LSTM+Transformer和GNN模型信息
- **回测分析 (backtest.html)**: 策略回测配置和结果展示
- **AI助手 (ai.html)**: 智能问答和分析助手

## 设计特色

- 🎨 深色科技风格主题
- 📱 响应式设计，支持移动端
- ✨ 流畅的动画效果
- 🎯 清晰的信息架构
- 💫 炫酷的视觉效果

## 技术栈

- HTML5
- CSS3 (包含动画和渐变效果)
- JavaScript (原生)
- Chart.js (图表库)

## 注意事项

1. 某些功能需要后端API支持（如数据加载、模型训练等），在纯静态环境下这些功能将显示占位内容
2. 建议使用现代浏览器（Chrome、Firefox、Edge等）以获得最佳体验
3. 如需完整功能，请配合后端Flask应用使用

## 后续开发

如需连接后端服务，需要：
1. 启动Flask后端服务器
2. 修改JS文件中的API端点
3. 处理跨域问题（CORS）

---

© 2026 ETF-ML. 华南理工大学 机器学习与金融科技团队
