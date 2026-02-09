"""完整流程集成测试

测试端到端的完整学习流程。
"""
import pytest
from datetime import datetime

from timem_evolve.dao.unified_dao import UnifiedDAO
from timem_evolve.services.learner_service import LearnerService
from timem_evolve.services.session_service import SessionService
from timem_evolve.models import (
    Session, SessionCreate, Message,
    Feedback, FeedbackCreate,
    Skill, Workflow
)


class TestSessionToSkillWorkflow:
    """从会话到技能的完整流程测试"""

    @pytest.fixture
    async def services(self, test_data_dir, knowledge_base_dir):
        """初始化服务"""
        dao = UnifiedDAO(
            data_dir=test_data_dir,
            use_registry=True
        )
        session_service = SessionService(dao)
        learner_service = LearnerService(dao)
        await dao.init_db()

        yield {
            "dao": dao,
            "session_service": session_service,
            "learner_service": learner_service
        }

    async def test_create_session_and_extract_skill(self, services):
        """测试创建会话并提取技能"""
        # 1. 创建成功的会话
        session_data = SessionCreate(
            task="学习 Python 装饰器",
            messages=[
                Message(role="user", content="什么是装饰器？"),
                Message(role="assistant", content="装饰器是一个接受函数并扩展其行为的函数。")
            ],
            outcome="success"
        )

        session = await services["session_service"].add_session(session_data)

        # 2. 验证会话已保存
        retrieved = await services["session_service"].get_session(session.session_id)
        assert retrieved is not None
        assert retrieved.task == "学习 Python 装饰器"

    async def test_save_skill_to_registry(self, services, sample_skill):
        """测试保存技能到 RegistryDAO"""
        # 1. 保存技能
        path = await services["dao"].save_skill(
            sample_skill,
            change_summary="测试保存"
        )

        # 2. 验证返回路径
        assert path is not None

        # 3. 验证技能已保存
        saved = await services["dao"].get_skill(sample_skill.skill_id)
        assert saved is not None
        assert saved.name == sample_skill.name

        # 4. 验证文件已创建
        skill_dir = services["dao"].registry_dao.kb_dir / "test" / sample_skill.skill_id
        assert (skill_dir / "SKILL.md").exists()
        assert (skill_dir / "evolution.log").exists()

    async def test_update_and_version_skill(self, services, sample_skill):
        """测试更新技能和版本管理"""
        # 1. 保存初始技能
        await services["dao"].save_skill(sample_skill, change_summary="初始版本")

        # 2. 更新技能名称
        updated = await services["dao"].update_skill(
            sample_skill.skill_id,
            updates={"name": "更新后的技能"},
            change_summary="优化名称"
        )

        assert updated is not None
        assert updated.name == "更新后的技能"

        # 3. 版本自增
        versioned = await services["dao"].increment_skill_version(
            sample_skill.skill_id,
            increment_type="minor",
            change_summary="功能增强"
        )

        assert versioned is not None
        assert versioned.metadata["version"] == "1.1.0"

    async def test_search_and_list_skills(self, services, sample_skill, sample_skill_2):
        """测试搜索和列出技能"""
        # 1. 保存多个技能
        await services["dao"].save_skill(sample_skill, change_summary="测试1")
        await services["dao"].save_skill(sample_skill_2, change_summary="测试2")

        # 2. 列出所有技能
        all_skills = await services["dao"].list_skills()
        assert len(all_skills) >= 2

        # 3. 按分类列出
        test_skills = await services["dao"].list_skills(category="test")
        for skill in test_skills:
            assert skill.metadata["category"] == "test"

        # 4. 搜索技能
        results = await services["dao"].search_skills(query="测试")
        assert len(results) >= 1

    async def test_export_and_import_skill(self, services, sample_skill):
        """测试导出和导入技能"""
        # 1. 保存技能
        await services["dao"].save_skill(sample_skill, change_summary="原始版本")

        # 2. 导出为 Markdown
        markdown = await services["dao"].export_skill_markdown(sample_skill.skill_id)
        assert markdown is not None
        assert "---" in markdown  # Frontmatter
        assert sample_skill.name in markdown

        # 3. 删除原始技能
        await services["dao"].delete_skill(sample_skill.skill_id)
        assert await services["dao"].get_skill(sample_skill.skill_id) is None

        # 4. 从 Markdown 导入
        imported = await services["dao"].import_skill_from_markdown(markdown)
        assert imported is not None
        assert imported.name == sample_skill.name

    async def test_evolution_log_tracking(self, services, sample_skill):
        """测试变更历史追踪"""
        # 1. 创建初始版本
        await services["dao"].save_skill(sample_skill, change_summary="初始创建")

        # 2. 多次更新
        for i in range(3):
            await services["dao"].update_skill(
                sample_skill.skill_id,
                updates={"description": f"第 {i+1} 次更新"},
                change_summary=f"更新 {i+1}"
            )

        # 3. 验证变更历史
        log = await services["dao"].get_evolution_log(sample_skill.skill_id)

        assert len(log) >= 4  # 初始 + 3次更新
        assert log[0]["summary"] == "初始创建"
        assert log[1]["summary"] == "更新 1"


class TestRegistryDAOPerformance:
    """RegistryDAO 性能测试"""

    async def test_bulk_save_performance(self, registry_dao):
        """测试批量保存性能"""
        import time

        skills = []
        for i in range(10):
            skill = Skill(
                skill_id=f"perf_skill_{i:03d}",
                name=f"性能测试技能 {i}",
                description="测试批量保存性能",
                metadata={"category": "performance"}
            )
            skills.append(skill)

        # 测量保存时间
        start = time.time()
        for skill in skills:
            await registry_dao.save_skill_container(skill, change_summary="性能测试")
        elapsed = time.time() - start

        # 验证
        assert elapsed < 30  # 应该在 30 秒内完成（实际应该更快）
        assert len(skills) == 10

    async def test_index_rebuild_performance(self, registry_dao, sample_skill):
        """测试索引重建性能"""
        import time

        # 准备数据
        for i in range(5):
            skill = Skill(
                skill_id=f"index_skill_{i}",
                name=f"索引测试技能 {i}",
                description="测试索引重建",
                metadata={"category": "index_test"}
            )
            await registry_dao.save_skill_container(skill, change_summary="测试")

        # 测量重建时间
        start = time.time()
        result = await registry_dao.rebuild_index()
        elapsed = time.time() - start

        # 验证
        assert elapsed < 10  # 应该在 10 秒内完成
        assert result["successful"] >= 5


class TestEdgeCases:
    """边界情况测试"""

    async def test_empty_skill_list(self, registry_dao):
        """测试空技能列表"""
        skills = await registry_dao.list_skill_containers()
        assert isinstance(skills, list)

    async def test_empty_search_results(self, registry_dao):
        """测试空搜索结果"""
        results = await registry_dao.search_skill_containers(
            query="完全不存在的技能名称"
        )
        assert len(results) == 0

    async def test_special_characters_in_skill(self, registry_dao):
        """测试特殊字符处理"""
        skill = Skill(
            skill_id="special_chars_001",
            name="特殊字符: @#$%",
            description="描述包含 '引号' 和 \"双引号\"",
            metadata={"category": "special"}
        )

        path = await registry_dao.save_skill_container(skill, change_summary="测试")

        # 验证能正确保存和读取
        saved = await registry_dao.get_skill_container(skill.skill_id)
        assert saved is not None
        assert saved.name == "特殊字符: @#$%"

    async def test_very_long_content(self, registry_dao):
        """测试长内容处理"""
        long_description = "。" * 10000  # 10000 个中文字符

        skill = Skill(
            skill_id="long_content_001",
            name="长内容技能",
            description=long_description,
            metadata={"category": "long"}
        )

        path = await registry_dao.save_skill_container(skill, change_summary="测试")

        # 验证能正确保存和读取
        saved = await registry_dao.get_skill_container(skill.skill_id)
        assert saved is not None
        assert len(saved.description) == 10000


class TestDataIntegrity:
    """数据完整性测试"""

    async def test_skill_persistence_after_restart(self, registry_dao, sample_skill):
        """测试技能在重启后的持久化"""
        # 1. 保存技能
        await registry_dao.save_skill_container(sample_skill, change_summary="初始")

        # 2. 模拟重启：创建新的 RegistryDAO 实例
        new_dao = RegistryDAO(str(registry_dao.kb_dir.parent))

        # 3. 验证数据仍然存在
        skill = await new_dao.get_skill_container(sample_skill.skill_id)
        assert skill is not None
        assert skill.name == sample_skill.name

    async def test_index_consistency(self, registry_dao, sample_skill, sample_skill_2):
        """测试索引一致性"""
        # 1. 保存多个技能
        await registry_dao.save_skill_container(sample_skill, change_summary="测试1")
        await registry_dao.save_skill_container(sample_skill_2, change_summary="测试2")

        # 2. 验证索引和实际文件一致
        index = await registry_dao._load_index()
        skills = await registry_dao.list_skill_containers(load_full=True)

        assert len(index["skills"]) == len(skills)

        # 3. 删除一个技能
        await registry_dao.delete_skill_container(sample_skill.skill_id)

        # 4. 验证索引已更新
        index_after = await registry_dao._load_index()
        assert sample_skill.skill_id not in index_after["skills"]
