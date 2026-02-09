"""Pytest 共享 fixtures

提供跨测试文件的共用测试数据和对象。
"""
import pytest
import asyncio
import tempfile
from pathlib import Path
from datetime import datetime

from timem_evolve.dao.memory_dao import MemoryDAO
from timem_evolve.dao.unified_dao import UnifiedDAO
from timem_evolve.dao.registry_dao import RegistryDAO
from timem_evolve.models import Skill, Workflow


# ==================== 测试数据 Fixtures ====================

@pytest.fixture(scope="session")
def event_loop():
    """创建事件循环"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_dir(tmp_path):
    """临时目录 fixture"""
    return tmp_path


@pytest.fixture
def test_data_dir(temp_dir):
    """测试数据目录"""
    data_dir = temp_dir / "data"
    data_dir.mkdir()
    return str(data_dir)


@pytest.fixture
def knowledge_base_dir(temp_dir):
    """知识库目录"""
    kb_dir = temp_dir / "knowledge_base"
    kb_dir.mkdir()
    return str(kb_dir)


# ==================== DAO Fixtures ====================

@pytest.fixture
def memory_dao(test_data_dir):
    """MemoryDAO 实例"""
    dao = MemoryDAO(data_dir=test_data_dir)
    # 清理文件
    dao.skills_path.write_text("[]")
    dao.rules_path.write_text("[]")
    dao.feedbacks_path.write_text("[]")
    return dao


@pytest.fixture
def registry_dao(knowledge_base_dir):
    """RegistryDAO 实例"""
    return RegistryDAO(knowledge_base_dir)


@pytest.fixture
async def registry_dao_initialized(knowledge_base_dir):
    """已初始化的 RegistryDAO"""
    dao = RegistryDAO(knowledge_base_dir)
    await dao.init_db()  # 如果有初始化逻辑
    return dao


@pytest.fixture
async def unified_dao_registry(test_data_dir, knowledge_base_dir):
    """使用 RegistryDAO 的 UnifiedDAO"""
    dao = UnifiedDAO(
        data_dir=test_data_dir,
        use_registry=True
    )
    await dao.init_db()
    return dao


@pytest.fixture
async def unified_dao_memory(test_data_dir):
    """使用 MemoryDAO 的 UnifiedDAO"""
    dao = UnifiedDAO(
        data_dir=test_data_dir,
        use_registry=False
    )
    await dao.init_db()
    return dao


# ==================== 技能 Fixtures ====================

@pytest.fixture
def sample_skill():
    """示例技能（用于测试）"""
    return Skill(
        skill_id="test_skill_001",
        name="测试技能",
        description="这是一个用于测试的技能",
        workflow=Workflow(
            steps=["步骤1: 准备工作", "步骤2: 执行操作", "步骤3: 验证结果"],
            sop="按照步骤依次执行，每步都要验证结果。"
        ),
        source_sessions=["session_001"],
        confidence=0.9,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        metadata={
            "category": "test",
            "version": "1.0.0",
            "tags": ["测试", "单元测试"],
            "author": "Test Suite",
            "decision_table": [
                {
                    "condition": "测试条件 A",
                    "action": "执行操作 A",
                    "priority": "高",
                    "note": "备注信息"
                }
            ],
            "rules_must_do": ["必须验证每一步结果"],
            "rules_dont": ["不能跳过任何步骤"]
        }
    )


@pytest.fixture
def sample_skill_2():
    """第二个示例技能"""
    return Skill(
        skill_id="test_skill_002",
        name="第二个测试技能",
        description="这是另一个用于测试的技能",
        workflow=Workflow(
            steps=["步骤 A", "步骤 B"],
            sop="标准操作流程描述"
        ),
        source_sessions=["session_002"],
        confidence=0.8,
        metadata={
            "category": "test",
            "version": "1.0.0",
            "tags": ["测试"]
        }
    )


@pytest.fixture
def sample_skill_different_category():
    """不同分类的技能"""
    return Skill(
        skill_id="test_skill_003",
        name="其他分类技能",
        description="在不同分类下的测试技能",
        workflow=Workflow(
            steps=["单一步骤"],
            sop="简化流程"
        ),
        metadata={
            "category": "other",
            "version": "1.0.0",
            "tags": ["其他"]
        }
    )


@pytest.fixture
async def saved_skill(registry_dao, sample_skill):
    """保存后的技能（带 change_summary）"""
    await registry_dao.save_skill_container(
        sample_skill,
        change_summary="测试保存"
    )
    return sample_skill


# ==================== Mock Fixtures ====================

@pytest.fixture
def mock_llm_response(mocker):
    """模拟 LLM 响应"""
    def _mock_response(content: str):
        mock = mocker.MagicMock()
        mock.content = content
        return mock
    return _mock_response


@pytest.fixture
def mock_skill_response():
    """模拟技能提炼响应"""
    import json
    return json.dumps({
        "name": "测试技能",
        "description": "描述",
        "steps": ["步骤1", "步骤2"],
        "sop": "标准流程",
        "confidence": 0.9
    }, ensure_ascii=False)
