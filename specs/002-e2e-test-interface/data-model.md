# Data Model: E2E Test Framework

**Feature**: 002-e2e-test-interface
**Date**: 2026-03-30
**Status**: Final

---

## Entity Overview

E2E 测试框架包含以下核心实体：

```
TestCase ──────┬──────────── TestFile
    │             │
    ├── TestResult
    └── TestSuite (aggregation)
```

---

## 1. TestCase (测试用例)

单个测试用例的定义，包含输入和期望输出。

### 属性

| 属性名 | 类型 | 必需 | 说明 |
|--------|------|------|------|
| `id` | `str` | ✅ | 唯一标识符 |
| `question` | `str` | ✅ | 提交给 RAG Service 的问题 |
| `expected_answer` | `str` | ⚠️ | 期望的答案（可选，用于相似度对比） |
| `source_docs` | `List[str]` | ⚠️ | 应该检索到的文档 ID 列表（用于验证） |
| `tags` | `List[str]` | ❌ | 标签（用于分组和过滤） |
| `metadata` | `Dict[str, Any]` | ❌ | 额外元数据 |

### 验证规则

- `id` 必须是字母数字下划线，符合 Python 变量命名规则
- `question` 不能为空
- `expected_answer` 如果提供，长度不能超过 10,000 字符
- `source_docs` 列表中的文档 ID 必须在知识库中存在（运行时验证）

### Pydantic 模型

```python
from pydantic import BaseModel, Field, field_validator
from typing import List, Dict, Any, Optional

class TestCase(BaseModel):
    """单个测试用例"""

    id: str = Field(..., pattern=r'^[a-zA-Z_][a-zA-Z0-9_]*$')
    question: str = Field(..., min_length=1)
    expected_answer: Optional[str] = Field(None, max_length=10000)
    source_docs: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator('id')
    @classmethod
    def id_must_be_valid(cls, v: str) -> str:
        if not v or v.isspace():
            raise ValueError("Test ID cannot be empty")
        return v
```

---

## 2. TestFile (测试文件)

包含一个或多个测试用例的文件。

### 属性

| 属性名 | 类型 | 必需 | 说明 |
|--------|------|------|------|
| `path` | `Path` | ✅ | 文件系统路径 |
| `format` | `FileFormat` | ✅ | 文件格式 (JSON/CSV/YAML/MD) |
| `test_cases` | `List[TestCase]` | ✅ | 测试用例列表 |

### 枚举定义

```python
from enum import Enum

class FileFormat(str, Enum):
    """支持的测试文件格式"""
    JSON = "json"
    CSV = "csv"
    YAML = "yaml"
    MARKDOWN = "markdown"
```

### Pydantic 模型

```python
from pathlib import Path

class TestFile(BaseModel):
    """测试文件"""

    path: Path
    format: FileFormat
    test_cases: List[TestCase] = Field(default_factory=list)

    class Config:
        arbitrary_types_allowed = True  # for Path
```

---

## 3. TestResult (测试结果)

单个测试用例的执行结果。

### 属性

| 属性名 | 类型 | 必需 | 说明 |
|--------|------|------|------|
| `test_id` | `str` | ✅ | 对应的 TestCase ID |
| `status` | `TestStatus` | ✅ | 测试状态 |
| `actual_answer` | `str` | ✅ | RAG Service 返回的实际答案 |
| `similarity_score` | `float` | ✅ | 相似度分数 (0-1) |
| `source_docs_retrieved` | `List[str]` | ✅ | 实际检索到的文档 ID |
| `source_docs_match` | `bool` | ✅ | 是否匹配期望的 source_docs |
| `error` | `Optional[str]` | ❌ | 错误信息（如果失败） |
| `latency_ms` | `float` | ✅ | 执行时间（毫秒） |
| `timestamp` | `datetime` | ✅ | 执行时间戳 |

### 枚举定义

```python
class TestStatus(str, Enum):
    """测试状态"""
    PASSED = "passed"           # 通过（相似度足够高且文档匹配）
    FAILED = "failed"           # 失败（相似度不足或文档不匹配）
    ERROR = "error"             # 错误（执行失败）
    SKIPPED = "skipped"         # 跳过（依赖问题）
```

### Pydantic 模型

```python
from datetime import datetime
from typing import List, Optional

class TestResult(BaseModel):
    """单个测试用例的执行结果"""

    test_id: str
    status: TestStatus
    actual_answer: str
    similarity_score: float = Field(ge=0.0, le=1.0)
    source_docs_retrieved: List[str] = Field(default_factory=list)
    source_docs_match: bool = False
    error: Optional[str] = None
    latency_ms: float = 0.0
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    @property
    def is_passed(self) -> bool:
        """判断测试是否通过"""
        if self.status != TestStatus.PASSED:
            return False
        # 可选的额外通过条件
        if self.source_docs and not self.source_docs_match:
            return False
        return True
```

---

## 4. TestReport (测试报告)

整个测试套件的聚合报告。

### 属性

| 属性名 | 类型 | 必需 | 说明 |
|--------|------|------|------|
| `suite_name` | `str` | ✅ | 测试套件名称（通常为文件名） |
| `total_tests` | `int` | ✅ | 总测试用例数 |
| `passed` | `int` | ✅ | 通过数量 |
| `failed` | `int` | ✅ | 失败数量 |
| `errors` | `int` | ✅ | 错误数量 |
| `skipped` | `int` | ✅ | 跳过数量 |
| `results` | `List[TestResult]` | ✅ | 所有测试结果详情 |
| `similarity_avg` | `float` | ✅ | 平均相似度 |
| `total_latency_ms` | `float` | ✅ | 总执行时间 |
| `timestamp` | `datetime` | ✅ | 报告生成时间 |

### Pydantic 模型

```python
class TestReport(BaseModel):
    """测试套件报告"""

    suite_name: str
    total_tests: int
    passed: int
    failed: int
    errors: int
    skipped: int
    results: List[TestResult]
    similarity_avg: float = 0.0
    total_latency_ms: float = 0.0
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    @property
    def pass_rate(self) -> float:
        """通过率 (0-1)"""
        if self.total_tests == 0:
            return 1.0
        return self.passed / self.total_tests

    @property
    def execution_time_s(self) -> float:
        """执行时间（秒）"""
        return self.total_latency_ms / 1000.0
```

---

## 5. TestConfig (测试配置)

测试执行的全局配置。

### 属性

| 属性名 | 类型 | 必需 | 默认值 | 说明 |
|--------|------|------|--------|------|
| `rag_service_url` | `str` | ✅ | `"http://localhost:8000"` | RAG Service 基础 URL |
| `timeout_seconds` | `int` | ❌ | `30` | 单个测试超时时间 |
| `max_concurrent` | `int` | ❌ | `1` | 最大并发数（1=顺序执行） |
| `similarity_threshold` | `float` | ❌ | `0.7` | 相似度通过阈值 |
| `retry_count` | `int` | ❌ | `3` | 失败重试次数 |
| `output_format` | `OutputFormat` | ❌ | `"console"` | 输出格式 |

### 枚举定义

```python
class OutputFormat(str, Enum):
    """输出格式"""
    CONSOLE = "console"
    JSON = "json"
    HTML = "html"
```

### Pydantic 模型

```python
from pydantic_settings import BaseSettings

class TestConfig(BaseSettings):
    """测试配置"""

    rag_service_url: str = "http://localhost:8000"
    timeout_seconds: int = 30
    max_concurrent: int = 1
    similarity_threshold: float = 0.7
    retry_count: int = 3
    output_format: OutputFormat = OutputFormat.CONSOLE

    class Config:
        env_prefix = "E2E_TEST_"
```

---

## 6. 关系图

```mermaid
erDiagram
    TestCase ||--o{ TestFile
    TestCase ||--o| TestResult
    TestResult ||--o{ TestReport
    TestFile }o--o{ TestConfig

    TestCase {
        +id: str
        +question: str
        +expected_answer: str
        +source_docs: List[str]
    }

    TestFile {
        +path: Path
        +format: FileFormat
        +test_cases: List[TestCase]
    }

    TestResult {
        +test_id: str
        +status: TestStatus
        +similarity_score: float
        +source_docs_match: bool
    }

    TestReport {
        +suite_name: str
        +passed: int
        +failed: int
        +results: List[TestResult]
    }
```

---

## 7. 数据流

```
TestFile (JSON/CSV/YAML/MD)
    ↓
Parser (解析器)
    ↓
List<TestCase> (测试用例)
    ↓
TestRunner (执行器)
    ↓
    for each TestCase:
        RAGClient.query(question)
        ↓
    TestResult (结果)
    ↓
TestReport (聚合报告)
```

---

## 8. 状态机

### TestResult 状态转换

```
[开始]
    ↓
[执行中] → (成功) → [PASSED] (如果 similarity >= threshold)
    ↓
         → (失败) → [FAILED] (如果 similarity < threshold)
    ↓
         → (错误) → [ERROR] (如果 API 调用失败)
```

---

## 9. 存储策略

### 无状态设计
- **不存储** 测试结果到数据库
- **仅输出** 到控制台/文件
- **可选** 导出 JSON 供后续分析

### 缓存策略
- **RAG API 响应不缓存**
- **测试文件** 读取时缓存（避免重复解析）

---

## 10. 验证规则

### 输入验证
- 测试 ID 唯一性（同一文件内）
- 问题非空
- 文件格式有效性

### 输出验证
- 相似度分数在 [0, 1] 范围
- 状态枚举值有效
- 时间戳单调递增

---

**状态**: ✅ Phase 1 完成 - 数据模型已定义
