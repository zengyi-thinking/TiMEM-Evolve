"""RegistryDAO 单元测试

测试 M.S.F.S 文件系统知识注册表的核心功能。
"""
import pytest
import asyncio
from datetime import datetime

from timem_evolve.dao.registry_dao import RegistryDAO
from timem_evolve.models import Skill, Workflow


class TestRegistryDAOInit:
    """RegistryDAO 初始化测试"""

    async def test_init_creates_directories(self, knowledge_base_dir):
        """测试初始化创建目录结构"""
        # Arrange & Act
        dao = RegistryDAO(knowledge_base_dir)

        # Assert
        assert dao.kb_dir.exists()
        assert dao.skills_dir.exists()
        assert dao.rules_dir.exists()
        assert dao.index_path.exists()

    async def test_init_existing_directory(self, registry_dao):
        """测试初始化已有目录"""
        # Arrange & Act
        # Assert - 不应抛出异常
        assert registry_dao.kb_dir.exists()


class TestRegistryDAOSave:
    """技能容器保存测试"""

    async def test_save_skill_container(self, registry_dao, sample_skill):
        """测试保存技能容器"""
        # Act
        path = await registry_dao.save_skill_container(
            sample_skill,
            change_summary="测试保存"
        )

        # Assert - 路径应该是 skills/test/skill_id
        assert path is not None
        assert (registry_dao.skills_dir / "test" / sample_skill.skill_id).exists()

        # 验证 SKILL.md 存在
        skill_md = registry_dao.skills_dir / "test" / sample_skill.skill_id / "SKILL.md"
        assert skill_md.exists()

        # 验证 evolution.log 存在
        evolution_log = registry_dao.skills_dir / "test" / sample_skill.skill_id / "evolution.log"
        assert evolution_log.exists()

        # 验证 RULES.md 存在
        rules_md = registry_dao.skills_dir / "test" / sample_skill.skill_id / "RULES.md"
        assert rules_md.exists()

        # 验证 impl 目录存在
        impl_dir = registry_dao.skills_dir / "test" / sample_skill.skill_id / "impl"
        assert impl_dir.exists()

    async def test_save_skill_updates_index(self, registry_dao, sample_skill):
        """测试保存技能后更新索引"""
        # Act
        await registry_dao.save_skill_container(
            sample_skill,
            change_summary="测试索引更新"
        )

        # Assert
        index = await registry_dao._load_index()
        assert sample_skill.skill_id in index["skills"]
        assert index["skills"][sample_skill.skill_id]["name"] == sample_skill.name

    async def test_save_skill_with_default_category(self, registry_dao):
        """测试保存技能使用默认分类"""
        # Arrange
        skill = Skill(
            skill_id="test_default_cat",
            name="默认分类技能",
            description="测试",
            metadata={}  # 没有 category
        )

        # Act
        path = await registry_dao.save_skill_container(skill, change_summary="测试")

        # Assert
        assert (registry_dao.skills_dir / "uncategorized" / "test_default_cat").exists()


class TestRegistryDAOGet:
    """技能容器获取测试"""

    async def test_get_skill_container(self, registry_dao, saved_skill):
        """测试获取技能容器"""
        # Act
        skill = await registry_dao.get_skill_container(saved_skill.skill_id)

        # Assert
        assert skill is not None
        assert skill.skill_id == saved_skill.skill_id
        assert skill.name == saved_skill.name
        assert skill.description == saved_skill.description

    async def test_get_skill_container_not_found(self, registry_dao):
        """测试获取不存在的技能"""
        # Act
        skill = await registry_dao.get_skill_container("non_existent_skill")

        # Assert
        assert skill is None

    async def test_get_skill_with_workflow(self, registry_dao, sample_skill):
        """测试获取包含工作流程的技能"""
        # Arrange
        await registry_dao.save_skill_container(sample_skill, change_summary="测试")

        # Act
        skill = await registry_dao.get_skill_container(sample_skill.skill_id)

        # Assert
        assert skill is not None
        assert len(skill.workflow.steps) == 3
        assert "按照步骤依次执行" in skill.workflow.sop

    async def test_get_skill_with_metadata(self, registry_dao, sample_skill):
        """测试获取包含元数据的技能"""
        # Arrange
        await registry_dao.save_skill_container(sample_skill, change_summary="测试")

        # Act
        skill = await registry_dao.get_skill_container(sample_skill.skill_id)

        # Assert
        assert skill is not None
        assert skill.metadata["category"] == "test"
        assert skill.metadata["version"] == "1.0.0"
        assert "测试" in skill.metadata["tags"]


class TestRegistryDAOList:
    """技能容器列表测试"""

    async def test_list_skill_containers(self, registry_dao, sample_skill, sample_skill_2):
        """测试列出技能容器"""
        # Arrange
        await registry_dao.save_skill_container(sample_skill, change_summary="测试1")
        await registry_dao.save_skill_container(sample_skill_2, change_summary="测试2")

        # Act
        skills = await registry_dao.list_skill_containers()

        # Assert
        assert len(skills) >= 2

    async def test_list_skill_containers_with_category_filter(self, registry_dao, sample_skill, sample_skill_different_category):
        """测试按分类过滤列出技能"""
        # Arrange
        await registry_dao.save_skill_container(sample_skill, change_summary="测试")
        await registry_dao.save_skill_container(sample_skill_different_category, change_summary="测试")

        # Act
        test_skills = await registry_dao.list_skill_containers(category="test")
        other_skills = await registry_dao.list_skill_containers(category="other")

        # Assert
        for skill in test_skills:
            assert skill.metadata["category"] == "test"

        for skill in other_skills:
            assert skill.metadata["category"] == "other"

    async def test_list_skill_containers_with_limit(self, registry_dao, sample_skill, sample_skill_2):
        """测试限制返回数量"""
        # Arrange
        await registry_dao.save_skill_container(sample_skill, change_summary="测试1")
        await registry_dao.save_skill_container(sample_skill_2, change_summary="测试2")

        # Act
        skills = await registry_dao.list_skill_containers(limit=1)

        # Assert
        assert len(skills) <= 1


class TestRegistryDAOSearch:
    """技能容器搜索测试"""

    async def test_search_skill_containers_by_name(self, registry_dao, sample_skill):
        """测试按名称搜索"""
        # Arrange
        await registry_dao.save_skill_container(sample_skill, change_summary="测试")

        # Act
        results = await registry_dao.search_skill_containers(query="测试技能")

        # Assert
        assert len(results) >= 1

    async def test_search_skill_containers_by_tag(self, registry_dao, sample_skill):
        """测试按标签搜索"""
        # Arrange
        await registry_dao.save_skill_container(sample_skill, change_summary="测试")

        # Act
        results = await registry_dao.search_skill_containers(query="单元测试")

        # Assert
        assert len(results) >= 1

    async def test_search_skill_containers_with_category_filter(self, registry_dao, sample_skill, sample_skill_different_category):
        """测试按分类过滤搜索"""
        # Arrange
        await registry_dao.save_skill_container(sample_skill, change_summary="测试")
        await registry_dao.save_skill_container(sample_skill_different_category, change_summary="测试")

        # Act
        results = await registry_dao.search_skill_containers(
            query="测试",
            category="other"
        )

        # Assert
        for skill in results:
            assert skill.metadata["category"] == "other"


class TestRegistryDAOUpdate:
    """技能容器更新测试"""

    async def test_update_skill_container(self, registry_dao, saved_skill):
        """测试更新技能"""
        # Act
        updated = await registry_dao.update_skill_container(
            skill_id=saved_skill.skill_id,
            updates={"name": "更新后的名称"},
            change_summary="测试更新"
        )

        # Assert
        assert updated is not None
        assert updated.name == "更新后的名称"

    async def test_update_skill_version_increment(self, registry_dao, saved_skill):
        """测试更新时版本号自增"""
        # Act
        updated = await registry_dao.update_skill_container(
            skill_id=saved_skill.skill_id,
            updates={"version_increment": "minor"},
            change_summary="版本更新"
        )

        # Assert
        assert updated is not None
        assert updated.metadata["version"] == "1.1.0"


class TestRegistryDAODelete:
    """技能容器删除测试"""

    async def test_delete_skill_container(self, registry_dao, saved_skill):
        """测试删除技能"""
        # Act
        success = await registry_dao.delete_skill_container(saved_skill.skill_id)

        # Assert
        assert success is True

        # 验证已删除
        skill = await registry_dao.get_skill_container(saved_skill.skill_id)
        assert skill is None

    async def test_delete_nonexistent_skill(self, registry_dao):
        """测试删除不存在的技能"""
        # Act
        success = await registry_dao.delete_skill_container("non_existent")

        # Assert
        assert success is False


class TestRegistryDAOEvolution:
    """变更历史测试"""

    async def test_get_evolution_log(self, registry_dao, saved_skill):
        """测试获取变更日志"""
        # Act
        log = await registry_dao.get_evolution_log(saved_skill.skill_id)

        # Assert
        assert len(log) >= 1
        assert log[0]["summary"] == "测试保存"

    async def test_evolution_log_format(self, registry_dao, saved_skill):
        """测试变更日志格式"""
        # Act
        log = await registry_dao.get_evolution_log(saved_skill.skill_id)

        # Assert
        assert "timestamp" in log[0]
        assert "version" in log[0]
        assert "summary" in log[0]


class TestRegistryDAOExport:
    """导出测试"""

    async def test_export_skill_markdown(self, registry_dao, saved_skill):
        """测试导出技能为 Markdown"""
        # Act
        markdown = await registry_dao.export_skill_markdown(saved_skill.skill_id)

        # Assert
        assert markdown is not None
        assert "---" in markdown  # Frontmatter
        assert saved_skill.name in markdown

    async def test_export_nonexistent_skill(self, registry_dao):
        """测试导出不存在的技能"""
        # Act
        markdown = await registry_dao.export_skill_markdown("non_existent")

        # Assert
        assert markdown is None


class TestRegistryDAOImport:
    """导入测试"""

    async def test_import_skill_from_markdown(self, registry_dao, sample_skill):
        """测试从 Markdown 导入技能"""
        # Arrange
        await registry_dao.save_skill_container(sample_skill, change_summary="原始")
        markdown = await registry_dao.export_skill_markdown(sample_skill.skill_id)

        # Act
        imported = await registry_dao.import_skill_from_markdown(markdown)

        # Assert
        assert imported is not None
        assert imported.name == sample_skill.name

    async def test_import_with_custom_skill_id(self, registry_dao, sample_skill):
        """测试导入时指定新技能 ID"""
        # Arrange
        await registry_dao.save_skill_container(sample_skill, change_summary="原始")
        markdown = await registry_dao.export_skill_markdown(sample_skill.skill_id)

        # Act
        imported = await registry_dao.import_skill_from_markdown(
            markdown,
            skill_id="new_skill_id"
        )

        # Assert
        assert imported is not None
        assert imported.skill_id == "new_skill_id"


class TestRegistryDAOIndex:
    """索引管理测试"""

    async def test_rebuild_index(self, registry_dao, sample_skill, sample_skill_2):
        """测试重建索引"""
        # Arrange
        await registry_dao.save_skill_container(sample_skill, change_summary="测试1")
        await registry_dao.save_skill_container(sample_skill_2, change_summary="测试2")

        # Act
        result = await registry_dao.rebuild_index()

        # Assert
        assert result["total_skills"] >= 2
        assert result["successful"] >= 2

    async def test_index_contains_skill_info(self, registry_dao, sample_skill):
        """测试索引包含技能信息"""
        # Arrange
        await registry_dao.save_skill_container(sample_skill, change_summary="测试")

        # Act
        index = await registry_dao._load_index()

        # Assert
        assert sample_skill.skill_id in index["skills"]
        info = index["skills"][sample_skill.skill_id]
        assert info["name"] == sample_skill.name
        assert info["category"] == "test"


class TestRegistryDAOVersion:
    """版本管理测试"""

    async def test_increment_version_patch(self, registry_dao, saved_skill):
        """测试 patch 版本自增"""
        # Act
        updated = await registry_dao.increment_skill_version(
            saved_skill.skill_id,
            increment_type="patch",
            change_summary="patch 更新"
        )

        # Assert
        assert updated.metadata["version"] == "1.0.1"

    async def test_increment_version_minor(self, registry_dao, saved_skill):
        """测试 minor 版本自增"""
        # Act
        updated = await registry_dao.increment_skill_version(
            saved_skill.skill_id,
            increment_type="minor",
            change_summary="minor 更新"
        )

        # Assert
        assert updated.metadata["version"] == "1.1.0"

    async def test_increment_version_major(self, registry_dao, saved_skill):
        """测试 major 版本自增"""
        # Act
        updated = await registry_dao.increment_skill_version(
            saved_skill.skill_id,
            increment_type="major",
            change_summary="major 更新"
        )

        # Assert
        assert updated.metadata["version"] == "2.0.0"

    async def test_increment_nonexistent_skill(self, registry_dao):
        """测试更新不存在的技能"""
        # Act
        updated = await registry_dao.increment_skill_version(
            "non_existent",
            increment_type="patch"
        )

        # Assert
        assert updated is None
