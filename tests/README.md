# TiMEM-Evolve 测试套件

## 目录结构

```
TiMEM-Evolve/
├── pytest.ini            # pytest 配置
├── tests/
│   ├── README.md         # 本文档
│   ├── conftest.py       # 共享 fixtures 和钩子
│   ├── fixtures/         # 测试数据 fixtures
│   ├── unit/            # 单元测试
│   │   ├── __init__.py
│   │   ├── test_registry_dao.py
│   │   ├── test_unified_dao.py
│   │   └── test_skill_model.py
│   └── integration/      # 集成测试
│       ├── __init__.py
│       ├── test_api.py
│       └── test_full_workflow.py
```

## 测试类型

### 单元测试 (tests/unit/)

| 文件 | 测试对象 | 覆盖范围 |
|------|---------|---------|
| `test_registry_dao.py` | RegistryDAO | save/get/update/delete/search/export/import/version |
| `test_unified_dao.py` | UnifiedDAO | 路由逻辑、后端选择、适配器模式 |
| `test_skill_model.py` | Skill 模型 | Workflow/SkillRouting/属性/序列化 |

### 集成测试 (tests/integration/)

| 文件 | 测试范围 |
|------|---------|
| `test_api.py` | FastAPI 端点 HTTP 响应 |
| `test_full_workflow.py` | 端到端学习流程 |

## 运行测试

```bash
# 安装测试依赖
pip install pytest pytest-asyncio pytest-cov httpx

# 运行所有测试
pytest

# 运行单元测试
pytest tests/unit/ -v

# 运行集成测试
pytest tests/integration/ -v

# 运行特定测试
pytest tests/unit/test_registry_dao.py::TestRegistryDAOSave -v
pytest tests/unit/test_registry_dao.py::TestRegistryDAOSave::test_save_skill_container -v

# 跳过慢速测试
pytest -m "not slow"

# 生成覆盖率报告
pytest --cov=timem_evolve --cov-report=term-missing --cov-report=html

# 查看 HTML 报告
open htmlcov/index.html
```

## 覆盖率目标

| 模块 | 目标覆盖率 |
|------|----------|
| RegistryDAO | 90% |
| UnifiedDAO | 85% |
| API 端点 | 80% |
| Skill 模型 | 90% |

## Fixtures

### conftest.py 提供的 fixtures

| Fixture | 类型 | 说明 |
|---------|------|------|
| `temp_dir` | pytest | pytest-tmp 临时目录 |
| `test_data_dir` | str | 测试数据目录路径 |
| `knowledge_base_dir` | str | 知识库目录路径 |
| `memory_dao` | MemoryDAO | MemoryDAO 实例 |
| `registry_dao` | RegistryDAO | RegistryDAO 实例 |
| `unified_dao_registry` | UnifiedDAO | 使用 RegistryDAO 的 UnifiedDAO |
| `unified_dao_memory` | UnifiedDAO | 使用 MemoryDAO 的 UnifiedDAO |
| `sample_skill` | Skill | 示例技能 |
| `sample_skill_2` | Skill | 第二个示例技能 |
| `saved_skill` | Skill | 已保存的示例技能 |

## 添加新测试

### 单元测试模板

```python
"""模块名 单元测试"""
import pytest

class TestTargetClass:
    """测试目标类"""

    async def test_method_name(self, fixture):
        """测试方法_名称"""
        # Arrange
        ...

        # Act
        result = ...

        # Assert
        assert result == expected
```

### 集成测试模板

```python
"""完整流程集成测试"""
import pytest

class TestFeatureWorkflow:
    """功能_流程测试"""

    async def test_end_to_end_flow(self, services):
        """测试端到端流程"""
        # 1. 准备
        ...

        # 2. 执行
        ...

        # 3. 验证
        ...
```

## CI/CD

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -e ".[dev]"
      - run: pytest
      - run: pytest --cov=timem_evolve --cov-report=xml
      - uses: codecov/codecov-action@v4
```
