# 大学物理知识图谱系统

基于图结构的大学物理学习系统，支持知识点拆解、推导路径展示和假设显式化。

## 项目概述

这是一个受约束的知识图谱编译器。给定一个物理知识点（方程、定律或概念），系统自动生成：
- **局部知识图**（向下依赖、向上应用）
- **推导路径与显式假设**
- **量纲验证与适用范围说明**
- **可交互的 HTML 图形展示**（基于 vis-network.js）

## 核心特性

1. **受限知识库优先**：LLM 只拼装，不从零发明
2. **图与层级分离**：底层是图，层级只是视图
3. **假设显式化**：推导边必须带 assumptions
4. **本地验证优先**：schema、DAG、量纲等必须本地验证
5. **文件驱动与测试先行**：所有中间结果落盘，失败有 debug.json

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境

```bash
cp .env.example .env
# 编辑 .env 文件，填入 DEEPSEEK_API_KEY
```

### 3. 启动前端应用

```bash
python run.py
# 浏览器打开 http://localhost:8501
```

### 4. CLI 构建（可选）

```bash
python scripts/build_topic.py --topic "伯努利方程" --down 2 --up 1
```

### 5. 查看结果

- 图数据：`artifacts/latest/graph.json`
- 交互式图：`artifacts/latest/graph.html`
- 报告：`artifacts/latest/report.md`
- 调试信息：`artifacts/latest/debug.json`

## 项目结构

```
physics_graph_demo/
├── app.py                 # Streamlit 前端应用入口
├── run.py                 # 启动脚本
├── requirements.txt       # Python 依赖
├── pyproject.toml         # 项目配置
├── .env.example           # 环境变量模板
├── configs/               # 配置文件（构建参数、prompt 模板、schema 版本）
│   └── domain_rules/      # 各领域物理规则
├── data/                  # 种子知识库
│   └── seeds/             # 各领域种子数据
├── schemas/               # JSON Schema 定义
├── src/                   # 核心源代码
│   ├── agents/            # 7 个 Agent（Router, Planner, Retriever, Decomposer, Verifier, Ranker, Renderer）
│   ├── validators/        # 5 个验证器（Schema, DAG, Assumption, Dimension, Duplicate）
│   ├── physics/           # 物理规则模块
│   ├── utils/             # 工具函数
│   └── exporters/         # 本体导出
├── scripts/               # CLI 脚本和工具
│   ├── build_topic.py     # 单主题构建
│   ├── install_deps.py    # 依赖安装
│   ├── checks/            # 验证/检查脚本
│   └── fixes/             # 数据修复脚本
├── tests/                 # 测试用例
├── docs/                  # 文档
└── artifacts/             # 构建输出（graph.json, graph.html 等）
```

## 系统架构

```
用户输入 topic
  -> RouterAgent：识别标准主题
  -> PlannerAgent：制定展开计划
  -> RetrieverAgent：从本地知识库取候选
  -> DecomposerAgent：组装候选子图
  -> VerifierAgent：执行多项校验
  -> RankerAgent：选择 canonical path
  -> RendererAgent：输出最终工件
```

## 数据模型

- **节点类型**：concept, quantity, definition, law, equation, model, assumption, math_tool, application, experiment, warning, intuition_card
- **边类型**：derives_from, requires, uses_math, assumes, equivalent_to, special_case_of, approximation_of, applies_to, motivated_by, related_to

## 验证体系

系统包含多层测试：
1. Schema 测试
2. 图结构测试（DAG 等）
3. Assumption 测试
4. 量纲测试
5. Benchmark 主题测试
6. 确定性测试
7. Renderer 输出测试

## 基准主题

系统支持 30+ 个基准物理主题，涵盖力学、热学、电磁学、光学、近代物理等 6 大领域。

## 技术栈

- **Python**: 3.9+
- **LLM**: DeepSeek API (deepseek-chat, deepseek-reasoner)
- **数据验证**: Pydantic, JSON Schema
- **图计算**: NetworkX
- **符号计算**: SymPy
- **前端**: Streamlit + vis-network.js

## 许可证

MIT License
