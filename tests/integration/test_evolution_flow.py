"""经验进化流程集成测试

测试：经验可进化 - 版本迭代和变更追踪
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

from timem_evolve.dao.registry_dao import RegistryDAO
from timem_evolve.dao.unified_dao import UnifiedDAO
from timem_evolve.models import Skill, Workflow


class TestSkillEvolution:
    """技能进化测试类"""

    @pytest.fixture
    async def registry_dao(self, tmp_path):
        """创建 RegistryDAO 实例"""
        kb_dir = str(tmp_path / "knowledge_base")
        dao = RegistryDAO(knowledge_base_dir=kb_dir)
        return dao

    @pytest.fixture
    async def unified_dao(self, tmp_path):
        """创建 UnifiedDAO 实例"""
        data_dir = str(tmp_path / "data")
        dao = UnifiedDAO(data_dir=data_dir, use_registry=True)
        await dao.init_db()
        return dao

    @pytest.fixture
    def sample_skill(self):
        """创建测试用技能"""
        return Skill(
            skill_id="evolution_test_skill_001",
            name="测试技能",
            description="这是一个用于测试进化功能的技能",
            workflow=Workflow(
                steps=["步骤1: 准备", "步骤2: 执行", "步骤3: 验证"],
                sop="按照步骤依次执行"
            ),
            confidence=0.9,
            metadata={
                "category": "test",
                "version": "1.0.0",
                "tags": ["测试", "进化"],
                "routing": {
                    "trigger_keywords": ["测试"],
                    "priority": 5
                }
            }
        )

    @pytest.mark.asyncio
    async def test_skill_version_patch(self, registry_dao, sample_skill):
        """补丁版本更新"""
        # 1. 保存初始技能
        await registry_dao.save_skill_container(sample_skill, change_summary="初始创建")

        # 2. 执行补丁更新
        updated = await registry_dao.increment_skill_version(
            skill_id=sample_skill.skill_id,
            increment_type="patch",
            change_summary="优化描述措辞"
        )

        # 3. 验证版本更新
        assert updated is not None
        assert updated.metadata.get("version") == "1.0.1"

        # 4. 验证 evolution.log
        evolution = await registry_dao.get_evolution_log(sample_skill.skill_id)
        assert len(evolution) >= 2  # 初始创建 + 1次更新

    @pytest.mark.asyncio
    async def test_skill_version_minor(self, registry_dao, sample_skill):
        """次版本更新 - 新增功能"""
        # 保存初始技能
        await registry_dao.save_skill_container(sample_skill, change_summary="初始创建")

        # 次版本更新
        updated = await registry_dao.increment_skill_version(
            skill_id=sample_skill.skill_id,
            increment_type="minor",
            change_summary="新增适用场景"
        )

        assert updated.metadata.get("version") == "1.1.0"

    @pytest.mark.asyncio
    async def test_skill_version_major(self, registry_dao, sample_skill):
        """主版本更新 - 重大重构"""
        # 保存初始技能
        await registry_dao.save_skill_container(sample_skill, change_summary="初始创建")

        # 主版本更新
        updated = await registry_dao.increment_skill_version(
            skill_id=sample_skill.skill_id,
            increment_type="major",
            change_summary="重构工作流程"
        )

        assert updated.metadata.get("version") == "2.0.0"

    @pytest.mark.asyncio
    async def test_evolution_log_completeness(self, registry_dao, sample_skill):
        """验证 evolution.log 完整性"""
        # 保存初始技能
        await registry_dao.save_skill_container(sample_skill, change_summary="初始创建")

        # 执行多次更新
        for i in range(3):
            await registry_dao.increment_skill_version(
                skill_id=sample_skill.skill_id,
                increment_type="patch",
                change_summary=f"更新 {i}"
            )

        # 验证日志完整性
        evolution = await registry_dao.get_evolution_log(sample_skill.skill_id)

        assert len(evolution) == 4  # 初始 + 3次更新

        for entry in evolution:
            assert "timestamp" in entry
            assert "version" in entry
            assert "summary" in entry
            assert "source" in entry

    @pytest.mark.asyncio
    async def test_version_increment_with_update(self, registry_dao, sample_skill):
        """测试带更新的版本递增"""
        # 保存初始技能
        await registry_dao.save_skill_container(sample_skill, change_summary="初始创建")

        # 更新并递增版本
        updated = await registry_dao.update_skill_container(
            skill_id=sample_skill.skill_id,
            updates={
                "description": "更新后的描述",
                "version_increment": "minor"
            },
            change_summary="更新描述并增加次版本"
        )

        assert updated.metadata.get("version") == "1.1.0"
        assert "更新后的描述" in updated.description

    @pytest.mark.asyncio
    async def test_nonexistent_skill_version_update(self, registry_dao):
        """测试不存在的技能版本更新"""
        result = await registry_dao.increment_skill_version(
            skill_id="nonexistent_skill",
            increment_type="patch"
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_evolution_log_format(self, registry_dao, sample_skill):
        """测试 evolution.log 格式"""
        # 保存初始技能
        await registry_dao.save_skill_container(sample_skill, change_summary="初始创建")

        # 更新技能
        await registry_dao.increment_skill_version(
            skill_id=sample_skill.skill_id,
            increment_type="patch",
            change_summary="测试更新"
        )

        # 读取 evolution.log 文件
        skill_dir = registry_dao.skills_dir / sample_skill.metadata["category"] / sample_skill.skill_id
        log_path = skill_dir / "evolution.log"

        assert log_path.exists()

        content = log_path.read_text(encoding="utf-8")
        lines = content.strip().split("\n")

        # 验证日志格式
        assert len(lines) >= 4  # 每次更新有2行（主行 + Source行），初始+更新=4行

        # 验证主行格式 [timestamp] v{version} - {summary}
        for line in lines:
            if line.strip() and not line.startswith("  Source:"):
                assert line.strip().startswith("[")
                assert "v" in line
                assert "-" in line

        # 验证 Source 行格式
        source_lines = [l for l in lines if l.startswith("  Source:")]
        assert len(source_lines) >= 2  # 每次更新都有 Source 行


class TestUnifiedDAOEvolution:
    """UnifiedDAO 进化功能测试"""

    @pytest.fixture
    async def unified_dao(self, tmp_path):
        data_dir = str(tmp_path / "data")
        dao = UnifiedDAO(data_dir=data_dir, use_registry=True)
        await dao.init_db()
        return dao

    @pytest.mark.asyncio
    async def test_increment_skill_version_via_unified_dao(self, unified_dao):
        """通过 UnifiedDAO 递增版本"""
        from timem_evolve.models import Skill, Workflow

        skill = Skill(
            skill_id="unified_test_skill_001",
            name="统一测试技能",
            description="通过 UnifiedDAO 测试进化功能",
            workflow=Workflow(steps=["步骤1"], sop="流程"),
            metadata={"category": "test", "version": "1.0.0"}
        )

        # 保存技能
        await unified_dao.save_skill(skill, change_summary="初始创建")

        # 递增版本
        updated = await unified_dao.increment_skill_version(
            skill_id=skill.skill_id,
            increment_type="patch",
            change_summary="统一测试更新"
        )

        assert updated is not None
        assert updated.metadata.get("version") == "1.0.1"

    @pytest.mark.asyncio
    async def test_get_evolution_log_via_unified_dao(self, unified_dao):
        """通过 UnifiedDAO 获取进化日志"""
        skill = Skill(
            skill_id="unified_test_skill_002",
            name="日志测试技能",
            description="测试获取进化日志",
            workflow=Workflow(steps=["步骤1"], sop="流程"),
            metadata={"category": "test", "version": "1.0.0"}
        )

        await unified_dao.save_skill(skill, change_summary="初始创建")
        await unified_dao.increment_skill_version(skill.skill_id, "patch", "更新1")
        await unified_dao.increment_skill_version(skill.skill_id, "patch", "更新2")

        evolution = await unified_dao.get_evolution_log(skill.skill_id)

        assert len(evolution) == 3
        assert evolution[-1]["summary"] == "更新2"


class TestVersionNumberLogic:
    """版本号逻辑测试"""

    @pytest.fixture
    def registry_dao(self, tmp_path):
        kb_dir = str(tmp_path / "kb")
        return RegistryDAO(knowledge_base_dir=kb_dir)

    def test_increment_patch(self, registry_dao):
        """测试 patch 递增"""
        assert registry_dao._increment_version("1.0.0", "patch") == "1.0.1"
        assert registry_dao._increment_version("2.3.5", "patch") == "2.3.6"

    def test_increment_minor(self, registry_dao):
        """测试 minor 递增"""
        assert registry_dao._increment_version("1.0.0", "minor") == "1.1.0"
        assert registry_dao._increment_version("2.3.5", "minor") == "2.4.0"

    def test_increment_major(self, registry_dao):
        """测试 major 递增"""
        assert registry_dao._increment_version("1.0.0", "major") == "2.0.0"
        assert registry_dao._increment_version("2.3.5", "major") == "3.0.0"

    def test_increment_invalid_version(self, registry_dao):
        """测试无效版本号处理"""
        # 应该回退到默认值 1.0.0
        assert registry_dao._increment_version("invalid", "patch") == "1.0.1"
        assert registry_dao._increment_version("v1.0.0", "patch") == "1.0.1"

    def test_increment_single_digit_version(self, registry_dao):
        """测试单数字版本号（会回退到默认格式）"""
        # 单数字版本号会回退到 1.0.0 然后递增
        assert registry_dao._increment_version("1", "minor") == "1.1.0"
        # "2" 无法正确解析，回退到 1.0.0 后 major 递增
        assert registry_dao._increment_version("2", "major") == "2.0.0"
