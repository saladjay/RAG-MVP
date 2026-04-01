# Technical Research: E2E Test Framework

**Feature**: 002-e2e-test-interface
**Date**: 2026-03-30
**Status**: Final

---

## Executive Summary

本文档记录 E2E 测试框架的技术选型研究结果。该框架用于验证 RAG Service 的完整功能，通过读取本地测试文件，调用 RAG API，对比实际结果与期望结果，并生成测试报告。

---

## 1. 文件解析器选型

### 需求分析
- 支持 4 种格式：JSON, CSV, YAML, Markdown
- 轻量级、无额外依赖
- 良好的错误提示

### 决策：使用 Python 标准库

| 格式 | 解析方案 | 决策理由 |
|------|----------|----------|
| **JSON** | `json` 模块 | 标准库，零依赖，支持验证 |
| **CSV** | `csv` 模块 | 标准库，处理引号转义 |
| **YAML** | `pyyaml` 包 | YAML 生态标准，文档完善 |
| **Markdown** | 正则 + `frontmatter` | 轻量解析代码块提取 |

**替代方案考虑**：
- `pandas` - 过于重量级
- `toml` - 不支持所需格式
- 自定义解析器 - 维护成本高

### 依赖声明
```toml
[dependencies]
pyyaml = "^6.0"
```

---

## 2. 相似度计算算法

### 需求分析
- 计算实际答案 vs 期望答案的相似度
- 0-1 或 0-100 分数
- 考虑语义相似度（不仅是关键词匹配）

### 决策：混合策略

| 场景 | 算法 | 决策理由 |
|------|------|----------|
| **基础相似度** | BLEU / ROUGE | NLP 领域标准，适合文本对比 |
| **语义相似度** | Cosine Similarity | 考虑语义，更准确 |
| **简单文本** | Jaccard / Levenshtein | 快速计算，适合短文本 |

**推荐实现**：
```python
# 基础实现：Levenshtein 距离
from difflib import SequenceMatcher

def calculate_similarity(text1: str, text2: str) -> float:
    """简单文本相似度计算 (0-1)"""
    return SequenceMatcher(None, text1, text2).ratio()

# 高级实现：Sentence Transformers (可选)
# from sentence_transformers import SentenceTransformer
# model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
# similarity = model.encode(text1) @ model.encode(text2)
```

### 依赖声明（可选高级实现）
```toml
[dependencies.optional]
sentence-transformers = "^2.2"  # 仅用于高级语义相似度
```

---

## 3. RAG Service API 集成

### 需求分析
- 调用 RAG Service 的 `/ai/agent` 接口
- 传递问题并获取答案和检索到的文档
- 处理网络错误、超时、服务不可用

### 决策：使用 httpx 异步客户端

| 方案 | 决策理由 |
|------|----------|
| **httpx** | 现代、异步、类型提示 |
| **requests** | 同步、简单，但不适合并发 |
| **aiohttp** | 底层、复杂，API 不友好 |

**实现示例**：
```python
import httpx
from typing import Dict, Any

class RAGClient:
    """RAG Service API 客户端"""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url

    async def query(self, question: str, trace_id: str = None) -> Dict[str, Any]:
        """调用 RAG Service 查询接口"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/v1/ai/agent",
                json={"question": question, "trace_id": trace_id}
            )
            response.raise_for_status()
            return response.json()
```

### 依赖声明
```toml
[dependencies]
httpx = "^0.27.0"
```

---

## 4. 测试报告生成

### 需求分析
- 输出格式：控制台 + JSON（可选 HTML）
- 指标：通过率、相似度分数、执行时间
- 详细的每个测试用例结果

### 决策：多格式输出

| 输出格式 | 实现方式 |
|----------|----------|
| **控制台** | `rich` 库（彩色表格、进度条） |
| **JSON** | 标准库 `json`（机器可读） |
| **HTML** | `jinja2` 模板（可选） |

### 依赖声明
```toml
[dependencies]
rich = "^13.7.0"
jinja2 = "^3.1.0"  # 可选
```

---

## 5. 项目类型与架构

### 项目类型
**CLI 工具** - 命令行测试框架

### 技术栈决策

| 层级 | 技术选择 |
|------|----------|
| **语言** | Python 3.11+ |
| **CLI 框架** | `Typer` (可选，也可直接 argparse) |
| **配置** | `pydantic-settings` |
| **日志** | `python-json-logger` |
| **测试** | `pytest`, `pytest-asyncio` |

### 源码结构
```
src/e2e_test/
├── __init__.py
├── cli.py              # CLI 入口
├── parsers/            # 文件解析器
│   ├── json_parser.py
│   ├── csv_parser.py
│   ├── yaml_parser.py
│   └── md_parser.py
├── runners/            # 测试执行器
│   └── test_runner.py
├── comparators/        # 结果对比器
│   ├── similarity.py
│   └── validator.py
├── reporters/           # 报告生成器
│   ├── console.py
│   └── json_report.py
├── clients/            # RAG API 客户端
│   └── rag_client.py
└── models/             # 数据模型
    └── test_case.py
```

---

## 6. 性能目标

### 需求分析
- 100 个测试用例 5 分钟内完成
- 支持并发执行（可选）

### 决策：顺序执行 + 可选并发

```python
import asyncio
from typing import List

class TestRunner:
    async def run_tests(self, tests: List[TestCase], parallel: bool = False):
        """执行测试用例"""
        if parallel:
            # 并发执行（实验性）
            tasks = [self._run_single_test(t) for t in tests]
            await asyncio.gather(*tasks)
        else:
            # 顺序执行（默认）
            for test in tests:
                await self._run_single_test(test)
```

---

## 7. 平台支持

### 目标平台
- **主要**: Linux, macOS
- **次要**: Windows (支持，但测试较少)

### Python 环境
- 使用 `uv` 管理依赖
- 虚拟环境：`.venv/`

---

## 8. 依赖关系

### 外部依赖
- **RAG Service**: 必须运行并可访问
- **网络**: 需要 python.org 和 GitHub API（可选，用于扩展）

### 内部依赖
- Spec 001 (RAG Service) - 必须先完成

---

## 9. 安全考虑

### 输入验证
- 测试文件大小限制（防止 DoS）
- 路径遍历保护（仅允许当前目录）
- 格式验证（防止注入攻击）

### API 安全
- 使用环境变量配置 RAG Service URL
- 不在日志中敏感信息

---

## 10. 总技术栈总结

```toml
[project]
name = "e2e-test"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    # Web
    "httpx>=0.27.0",
    "pydantic>=2.5.0",
    # File Parsing
    "pyyaml>=6.0",
    # CLI (optional)
    "typer>=0.12.0",
    # Output
    "rich>=13.7.0",
    "jinja2>=3.1.0",  # optional
    # Logging
    "python-json-logger>=2.0.0",
]
[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=4.1.0",
]

[project.scripts]
# CLI entry points
e2e = "e2e_test.cli:main"
```

---

## 11. 关键技术决策汇总

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 语言 | Python 3.11+ | 与 RAG Service 一致，生态丰富 |
| 文件解析 | 标准库 + pyyaml | 轻量、可靠 |
| HTTP 客户端 | httpx | 异步、现代、类型友好 |
| 相似度计算 | Levenshtein (基础) + Sentence Transformers (可选) | 简单优先，高级可选 |
| 报告输出 | rich (控制台) + JSON | 用户友好 + 机器可读 |
| 测试框架 | pytest | 与项目一致 |
| 并发执行 | asyncio.gather (可选) | 灵活、可控 |

---

## 12. 技术风险与缓解

| 风险 | 缓解措施 |
|------|----------|
| YAML 解析兼容性 | 使用标准 `pyyaml`，提供格式示例 |
| 相似度计算精度 | 提供配置选项，支持多种算法 |
| RAG Service 不稳定 | 重试机制、详细错误日志 |
| 大文件性能 | 流式解析、大小限制 |
| 跨平台兼容性 | 使用 `pathlib`，测试覆盖主要平台 |

---

**状态**: ✅ Phase 0 完成 - 所有关键技术决策已确定
