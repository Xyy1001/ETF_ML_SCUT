# ETF-ML展示系统

基于深度学习的智能股票预测与分析展示平台，面向最终用户提供数据展示、模型展示、回测分析和AI智能助手功能。

## 功能特性

- **🏠 首页展示**：系统概览、功能介绍、性能指标展示
- **📊 数据展示**：原始股票数据和技术指标数据查看、下载
- **🧠 模型展示**：LSTM+Transformer和GNN模型信息展示
- **📈 回测分析**：策略回测、净值曲线、性能指标分析
- **🤖 AI助手**：知识问答、数据分析、报告生成、文件下载
- **💬 看板娘**：浮动智能助手，简单问答和快速导航

## 技术架构

### 后端
- Flask 2.3.3
- Pandas 2.1.0
- NumPy 1.24.3

### 前端
- HTML5 + CSS3
- 原生JavaScript
- Chart.js 图表库
- 蓝紫色渐变高智风格设计

### 机器学习模型
- **LSTM+Transformer**：股票价格预测
  - 输入：60天历史数据 + 7种技术指标
  - 输出：10日价格预测
  - 准确率：85%+

- **GNN图神经网络**：风险管理
  - 图注意力网络(GAT)
  - 预测协方差矩阵
  - 投资组合优化

## 快速开始

### 安装依赖

```bash
cd G-Web
pip install -r requirements.txt
```

### 运行服务

```bash
python app.py
```

服务将在 `http://localhost:5001` 启动

### 访问页面

- 首页：http://localhost:5001/
- 数据展示：http://localhost:5001/data
- 模型展示：http://localhost:5001/models
- 回测分析：http://localhost:5001/backtest
- AI助手：http://localhost:5001/ai

## 目录结构

```
G-Web/
├── app.py                 # Flask后端主程序
├── requirements.txt       # Python依赖
├── README.md             # 说明文档
├── templates/            # HTML模板
│   ├── index.html       # 首页
│   ├── data.html        # 数据展示页
│   ├── models.html      # 模型展示页
│   ├── backtest.html    # 回测分析页
│   └── ai.html          # AI助手页
└── static/              # 静态资源
    ├── style.css        # 全局样式
    ├── index.js         # 首页脚本
    ├── data.css         # 数据页样式
    ├── data.js          # 数据页脚本
    ├── ai.css           # AI页样式
    ├── ai.js            # AI页脚本
    ├── mascot.css       # 看板娘样式
    └── mascot.js        # 看板娘脚本
```

## API接口

### 数据相关
- `GET /api/data/summary` - 获取数据概览
- `GET /api/data/stock/<code>` - 获取指定股票数据

### 模型相关
- `GET /api/models/summary` - 获取模型概览

### 回测相关
- `POST /api/backtest/run` - 运行回测分析

### AI助手相关
- `POST /api/ai/chat` - AI聊天接口
- `GET /api/ai/knowledge` - 获取知识库分类
- `GET /api/ai/suggest` - 获取问题建议
- `POST /api/ai/analysis` - 生成分析报告
- `POST /api/ai/download` - 下载文件

### 看板娘相关
- `POST /api/mascot/chat` - 看板娘简单问答

## 知识库分类

系统AI助手包含8大知识库分类：
1. 系统介绍
2. 股票预测
3. 风险控制
4. 回测分析
5. 技术指标
6. 数据来源
7. 模型架构
8. 使用帮助

## 设计特色

- 🎨 蓝紫色渐变主题 (#667eea → #764ba2)
- 🌙 深色模式设计
- ✨ 毛玻璃效果 (backdrop-filter)
- 🎯 卡片式布局
- 📱 响应式设计
- 🎭 平滑动画过渡

## 注意事项

1. 本系统为**展示型系统**，面向不可操作用户
2. 数据和模型路径配置在 `app.py` 中
3. 回测功能当前为模拟数据，需接入 `C-Backtest/backtest.py`
4. AI问答基于关键词匹配，可升级为大模型接入

## 开发团队

华南理工大学 机器学习与金融科技团队

## 许可证

© 2026 ETF-ML. All rights reserved.
