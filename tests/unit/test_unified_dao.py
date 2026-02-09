"""UnifiedDAO 单元测试

测试统一数据访问对象的适配器功能和路由逻辑。
"""
import pytest
import asyncio

from timem_evolve.dao.unified_dao import UnifiedDAO


class TestUnifiedDAOInit:
    """UnifiedDAO 初始化测试"""

    async def test_init_with_registry_true(self, test_data_dir, knowledge_base_dir):
        """测试使用 RegistryDAO 初始化"""
        # Act
        dao = UnifiedDAO(
            data_dir=test_data_dir,
            use_registry=True
        )

        # Assert
        assert dao.use_registry is True
        assert dao.is_using_registry() is True

    async def test_init_with_registry_false(self, test_data_dir):
        """测试使用 MemoryDAO 初始化"""
        # Act
        dao = UnifiedDAO(
            data_dir=test_data_dir,
            use_registry=False
        )

        # Assert
        assert dao.use_registry is False
        assert dao.is_using_registry() is False

    async def test_init_from_env_var_true(self, test_data_dir, knowledge_base_dir, mocker):
        """测试从环境变量读取 USE_SKILL_REGISTRY=true"""
        # Arrange
        mocker.patch("timem_evolve.dao.unified_dao.os.getenv", return_value="true")

        # Act
        dao = UnifiedDAO(data_dir=test_data_dir, use_registry=None)

        # Assert
        assert dao.use_registry is True

    async def test_init_from_env_var_false(self, test_data_dir, mocker):
        """测试从环境变量读取 USE_SKILL_REGISTRY=false"""
        # Arrange
        mocker.patch("timem_evolve.dao.unified_dao.os.getenv", return_value="false")

        # Act
        dao = UnifiedDAO(data_dir=test_data_dir, use_registry=None)

        # Assert
        assert dao.use_registry is False


class TestUnifiedDAOBackendInfo:
    """后端信息测试"""

    async def test_get_backend_info_registry(self, unified_dao_registry):
        """测试 RegistryDAO 后端信息"""
        # Act
        info = unified_dao_registry.get_backend_info()

        # Assert
        assert info["use_skill_registry"] is True
        assert "RegistryDAO" in info["skills_backend"]
        assert "MemoryDAO" in info["sessions_backend"]

    async def test_get_backend_info_memory(self, unified_dao_memory):
        """测试 MemoryDAO 后端信息"""
        # Act
        info = unified_dao_memory.get_backend_info()

        # Assert
        assert info["use_skill_registry"] is False
        assert "MemoryDAO" in info["skills_backend"]
        assert info["knowledge_base_dir"] is None


class TestUnifiedDAOSkills:
    """技能操作测试"""

    async def test_save_skill_registry(self, unified_dao_registry, sample_skill):
        """测试使用 RegistryDAO 保存技能"""
        # Act
        path = await unified_dao_registry.save_skill(
            sample_skill,
            change_summary="测试保存"
        )

        # Assert
        assert path is not None

        # 验证技能已保存
        saved = await unified_dao_registry.get_skill(sample_skill.skill_id)
        assert saved is not None
        assert saved.name == sample_skill.name

    async def test_save_skill_memory(self, unified_dao_memory, sample_skill):
        """测试使用 MemoryDAO 保存技能"""
        # Act
        path = await unified_dao_memory.save_skill(sample_skill)

        # Assert
        assert path is None  # MemoryDAO 返回 None

        # 验证技能已保存
        saved = await unified_dao_memory.get_skill(sample_skill.skill_id)
        assert saved is not None
        assert saved.name == sample_skill.name

    async def test_get_skill_registry(self, unified_dao_registry, sample_skill):
        """测试使用 RegistryDAO 获取技能"""
        # Arrange
        await unified_dao_registry.save_skill(sample_skill, change_summary="测试")

        # Act
        skill = await unified_dao_registry.get_skill(sample_skill.skill_id)

        # Assert
        assert skill is not None
        assert skill.skill_id == sample_skill.skill_id

    async def test_get_skill_memory(self, unified_dao_memory, sample_skill):
        """测试使用 MemoryDAO 获取技能"""
        # Arrange
        await unified_dao_memory.save_skill(sample_skill)

        # Act
        skill = await unified_dao_memory.get_skill(sample_skill.skill_id)

        # Assert
        assert skill is not None
        assert skill.skill_id == sample_skill.skill_id

    async def test_list_skills_registry(self, unified_dao_registry, sample_skill, sample_skill_2):
        """测试使用 RegistryDAO 列出技能"""
        # Arrange
        await unified_dao_registry.save_skill(sample_skill, change_summary="测试1")
        await unified_dao_registry.save_skill(sample_skill_2, change_summary="测试2")

        # Act
        skills = await unified_dao_registry.list_skills()

        # Assert
        assert len(skills) >= 2

    async def test_list_skills_with_category_registry(self, unified_dao_registry, sample_skill, sample_skill_different_category):
        """测试使用 RegistryDAO 按分类列出技能"""
        # Arrange
        await unified_dao_registry.save_skill(sample_skill, change_summary="测试")
        await unified_dao_registry.save_skill(sample_skill_different_category, change_summary="测试")

        # Act
        test_skills = await unified_dao_registry.list_skills(category="test")
        other_skills = await unified_dao_registry.list_skills(category="other")

        # Assert
        for skill in test_skills:
            assert skill.metadata["category"] == "test"

    async def test_search_skills_registry(self, unified_dao_registry, sample_skill):
        """测试使用 RegistryDAO 搜索技能"""
        # Arrange
        await unified_dao_registry.save_skill(sample_skill, change_summary="测试")

        # Act
        results = await unified_dao_registry.search_skills(query="测试")

        # Assert
        assert len(results) >= 1

    async def test_update_skill_registry(self, unified_dao_registry, sample_skill):
        """测试使用 RegistryDAO 更新技能"""
        # Arrange
        await unified_dao_registry.save_skill(sample_skill, change_summary="测试")

        # Act
        updated = await unified_dao_registry.update_skill(
            sample_skill.skill_id,
            updates={"name": "更新后的名称"},
            change_summary="测试更新"
        )

        # Assert
        assert updated is not None
        assert updated.name == "更新后的名称"

    async def test_delete_skill_registry(self, unified_dao_registry, sample_skill):
        """测试使用 RegistryDAO 删除技能"""
        # Arrange
        await unified_dao_registry.save_skill(sample_skill, change_summary="测试")

        # Act
        success = await unified_dao_registry.delete_skill(sample_skill.skill_id)

        # Assert
        assert success is True
        assert await unified_dao_registry.get_skill(sample_skill.skill_id) is None

    async def test_delete_skill_memory(self, unified_dao_memory, sample_skill):
        """测试使用 MemoryDAO 删除技能"""
        # Arrange
        await unified_dao_memory.save_skill(sample_skill)

        # Act
        success = await unified_dao_memory.delete_skill(sample_skill.skill_id)

        # Assert
        assert success is False  # MemoryDAO 不支持删除


class TestUnifiedDAOExtension:
    """扩展操作测试（RegistryDAO 专属）"""

    async def test_get_evolution_log_registry(self, unified_dao_registry, sample_skill):
        """测试获取变更历史"""
        # Arrange
        await unified_dao_registry.save_skill(sample_skill, change_summary="测试")

        # Act
        log = await unified_dao_registry.get_evolution_log(sample_skill.skill_id)

        # Assert
        assert len(log) >= 1

    async def test_get_evolution_log_memory(self, unified_dao_memory, sample_skill):
        """测试获取变更历史（MemoryDAO）"""
        # Arrange
        await unified_dao_memory.save_skill(sample_skill)

        # Act
        log = await unified_dao_memory.get_evolution_log(sample_skill.skill_id)

        # Assert
        assert log == []  # MemoryDAO 不支持

    async def test_export_skill_markdown_registry(self, unified_dao_registry, sample_skill):
        """测试导出 Markdown"""
        # Arrange
        await unified_dao_registry.save_skill(sample_skill, change_summary="测试")

        # Act
        markdown = await unified_dao_registry.export_skill_markdown(sample_skill.skill_id)

        # Assert
        assert markdown is not None
        assert "---" in markdown

    async def test_export_skill_markdown_memory(self, unified_dao_memory, sample_skill):
        """测试导出 Markdown（MemoryDAO）"""
        # Arrange
        await unified_dao_memory.save_skill(sample_skill)

        # Act
        markdown = await unified_dao_memory.export_skill_markdown(sample_skill.skill_id)

        # Assert
        assert markdown is None  # MemoryDAO 不支持

    async def test_import_skill_from_markdown_registry(self, unified_dao_registry, sample_skill):
        """测试从 Markdown 导入"""
        # Arrange
        await unified_dao_registry.save_skill(sample_skill, change_summary="原始")
        markdown = await unified_dao_registry.export_skill_markdown(sample_skill.skill_id)

        # Act
        imported = await unified_dao_registry.import_skill_from_markdown(markdown)

        # Assert
        assert imported is not None
        assert imported.name == sample_skill.name

    async def test_import_skill_from_markdown_memory(self, unified_dao_memory, sample_skill):
        """测试从 Markdown 导入（MemoryDAO）"""
        # Act
        imported = await unified_dao_memory.import_skill_from_markdown("test")

        # Assert
        assert imported is None  # MemoryDAO 不支持

    async def test_rebuild_index_registry(self, unified_dao_registry, sample_skill):
        """测试重建索引"""
        # Arrange
        await unified_dao_registry.save_skill(sample_skill, change_summary="测试")

        # Act
        result = await unified_dao_registry.rebuild_index()

        # Assert
        assert "successful" in result

    async def test_rebuild_index_memory(self, unified_dao_memory):
        """测试重建索引（MemoryDAO）"""
        # Act
        result = await unified_dao_memory.rebuild_index()

        # Assert
        assert "message" in result
        assert "MemoryDAO" in result["message"]

    async def test_increment_skill_version_registry(self, unified_dao_registry, sample_skill):
        """测试版本更新"""
        # Arrange
        await unified_dao_registry.save_skill(sample_skill, change_summary="测试")

        # Act
        updated = await unified_dao_registry.increment_skill_version(
            sample_skill.skill_id,
            increment_type="minor"
        )

        # Assert
        assert updated is not None
        assert updated.metadata["version"] == "1.1.0"

    async def test_increment_skill_version_memory(self, unified_dao_memory, sample_skill):
        """测试版本更新（MemoryDAO）"""
        # Arrange
        await unified_dao_memory.save_skill(sample_skill)

        # Act
        updated = await unified_dao_memory.increment_skill_version(
            sample_skill.skill_id,
            increment_type="minor"
        )

        # Assert
        assert updated is None  # MemoryDAO 不支持


class TestUnifiedDAORouting:
    """路由逻辑测试"""

    async def test_skills_route_to_registry(self, unified_dao_registry, sample_skill):
        """验证技能操作路由到 RegistryDAO"""
        # Act
        path = await unified_dao_registry.save_skill(sample_skill, change_summary="测试")

        # Assert - RegistryDAO 返回路径
        assert path is not None

    async def test_skills_route_to_memory(self, unified_dao_memory, sample_skill):
        """验证技能操作路由到 MemoryDAO"""
        # Act
        path = await unified_dao_memory.save_skill(sample_skill)

        # Assert - MemoryDAO 返回 None
        assert path is None

    async def test_sessions_always_memory(self, unified_dao_registry, unified_dao_memory):
        """验证会话始终使用 MemoryDAO"""
        from timem_evolve.models import Session, SessionCreate, Message

        session_data = SessionCreate(
            task="测试会话",
            messages=[Message(role="user", content="测试")],
            outcome="success"
        )
        session = Session(**session_data.model_dump())

        # RegistryDAO 和 MemoryDAO 都使用 MemoryDAO 处理会话
        await unified_dao_registry.init_db()
        await unified_dao_registry.save_session(session)

        retrieved = await unified_dao_registry.get_session(session.session_id)
        assert retrieved is not None

        await unified_dao_memory.init_db()
        await unified_dao_memory.save_session(session)

        retrieved = await unified_dao_memory.get_session(session.session_id)
        assert retrieved is not None

    async def test_rules_always_memory(self, unified_dao_registry, unified_dao_memory):
        """验证规则始终使用 MemoryDAO"""
        from timem_evolve.models import Rule

        rule = Rule(
            name="测试规则",
            description="测试规则描述",
            constraint="测试约束",
            reason="测试原因"
        )

        # RegistryDAO 使用 MemoryDAO 处理规则
        unified_dao_registry.save_rule(rule)
        retrieved = unified_dao_registry.get_rule(rule.rule_id)
        assert retrieved is not None
