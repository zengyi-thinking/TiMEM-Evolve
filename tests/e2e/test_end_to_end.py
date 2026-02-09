"""端到端测试 - 完整工作流验证

测试：TiMEM-Evolve 核心特性的端到端集成
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
import json

from timem_evolve.services.learner_service import LearnerService
from timem_evolve.dao.unified_dao import UnifiedDAO
from timem_evolve.dao.registry_dao import RegistryDAO
from timem_evolve.models import Skill, Rule, Workflow


class TestSkillEvolutionWorkflow:
    """技能进化工作流测试"""

    @pytest.fixture
    async def registry_dao(self, tmp_path):
        """创建 RegistryDAO"""
        kb_dir = str(tmp_path / "knowledge_base")
        return RegistryDAO(kb_dir)

    @pytest.mark.asyncio
    async def test_skill_evolution_workflow(self, registry_dao):
        """技能进化工作流"""
        # 1. 初始技能
        initial_skill = Skill(
            skill_id="e2e_evolution_001",
            name="测试进化技能",
            description="初始版本描述",
            workflow=Workflow(
                steps=["步骤1", "步骤2"],
                sop="标准流程"
            ),
            metadata={
                "category": "test",
                "version": "1.0.0",
                "tags": ["测试"]
            }
        )
        await registry_dao.save_skill_container(initial_skill, change_summary="初始创建")

        # 2. 进化流程
        for i in range(3):
            updated = await registry_dao.increment_skill_version(
                skill_id=initial_skill.skill_id,
                increment_type="patch",
                change_summary=f"优化版本 {i+1}"
            )

        # 3. 验证进化结果
        final_skill = await registry_dao.get_skill_container(initial_skill.skill_id)
        assert final_skill.metadata.get("version") == "1.0.3"

        # 4. 验证 evolution.log
        evolution = await registry_dao.get_evolution_log(initial_skill.skill_id)
        assert len(evolution) == 4  # 初始 + 3次更新


class TestSkillReuseWorkflow:
    """技能复用工作流测试"""

    @pytest.fixture
    async def registry_dao(self, tmp_path):
        """创建 RegistryDAO"""
        kb_dir = str(tmp_path / "knowledge_base")
        return RegistryDAO(kb_dir)

    @pytest.mark.asyncio
    async def test_skill_reuse_workflow(self, registry_dao):
        """技能复用工作流"""
        # 1. 创建多个技能
        skills_data = [
            ("代码解释", "communication", ["解释", "代码"]),
            ("错误诊断", "debugging", ["报错", "错误"]),
            ("文档编写", "writing", ["文档", "注释"]),
        ]

        for name, category, keywords in skills_data:
            skill = Skill(
                skill_id=f"reuse_{name}",
                name=name,
                description=f"这是{name}",
                workflow=Workflow(steps=["步骤1"], sop="流程"),
                metadata={
                    "category": category,
                    "version": "1.0.0",
                    "routing": {
                        "trigger_keywords": keywords,
                        "priority": 5
                    }
                }
            )
            await registry_dao.save_skill_container(skill, change_summary=f"创建{name}")

        # 2. 验证技能已存储
        all_skills = await registry_dao.list_skill_containers(category=None)
        assert len(all_skills) >= 3

        # 3. 搜索复用
        matched = await registry_dao.search_skill_containers("解释代码")
        assert len(matched) >= 1

        matched = await registry_dao.search_skill_containers("Python 报错")
        assert len(matched) >= 1


class TestMarkdownFileSync:
    """Markdown 文件同步测试"""

    @pytest.fixture
    async def registry_dao(self, tmp_path):
        """创建 RegistryDAO"""
        kb_dir = str(tmp_path / "kb")
        return RegistryDAO(kb_dir)

    @pytest.mark.asyncio
    async def test_markdown_consistency(self, registry_dao):
        """Markdown 内容一致性测试"""
        # 1. 创建技能
        skill = Skill(
            skill_id="markdown_test_001",
            name="Markdown 一致性测试",
            description="测试 Markdown 文件与内存对象的一致性",
            workflow=Workflow(
                steps=["步骤1: 创建", "步骤2: 验证"],
                sop="标准操作流程"
            ),
            metadata={
                "category": "test",
                "version": "1.0.0",
                "tags": ["测试", "markdown"]
            }
        )

        await registry_dao.save_skill_container(skill, change_summary="初始创建")

        # 2. 读取并验证
        read_skill = await registry_dao.get_skill_container(skill.skill_id)

        assert read_skill.name == skill.name
        assert read_skill.description == skill.description
        assert read_skill.workflow.steps == skill.workflow.steps
        assert read_skill.metadata.get("version") == "1.0.0"

        # 3. 更新
        await registry_dao.update_skill_container(
            skill_id=skill.skill_id,
            updates={"description": "更新后的描述"},
            change_summary="更新"
        )

        # 4. 再次读取验证
        updated_skill = await registry_dao.get_skill_container(skill.skill_id)
        assert "更新后的描述" in updated_skill.description


class TestPerformanceAndReliability:
    """性能和可靠性测试"""

    @pytest.fixture
    async def registry_dao(self, tmp_path):
        """创建 RegistryDAO"""
        kb_dir = str(tmp_path / "kb")
        return RegistryDAO(kb_dir)

    @pytest.mark.asyncio
    async def test_bulk_skill_operations(self, registry_dao):
        """批量技能操作"""
        # 批量创建
        skills_count = 10
        for i in range(skills_count):
            skill = Skill(
                skill_id=f"bulk_test_{i:03d}",
                name=f"批量测试技能 {i}",
                description=f"批量创建的技能 {i}",
                workflow=Workflow(steps=["步骤1"], sop="流程"),
                metadata={"category": "bulk", "version": "1.0.0"}
            )
            await registry_dao.save_skill_container(skill, change_summary=f"创建 {i}")

        # 验证数量
        all_skills = await registry_dao.list_skill_containers(category="bulk")
        assert len(all_skills) >= skills_count

        # 重建索引
        result = await registry_dao.rebuild_index()
        assert result["successful"] >= skills_count

    @pytest.mark.asyncio
    async def test_concurrent_version_updates(self, registry_dao):
        """并发版本更新测试（串行执行）"""
        skill = Skill(
            skill_id="concurrent_test_001",
            name="并发测试",
            description="测试",
            workflow=Workflow(steps=["步骤1"], sop="流程"),
            metadata={"category": "test", "version": "1.0.0"}
        )

        await registry_dao.save_skill_container(skill, change_summary="初始")

        # 串行执行多次更新
        for i in range(5):
            await registry_dao.increment_skill_version(
                skill_id=skill.skill_id,
                increment_type="patch",
                change_summary=f"更新 {i+1}"
            )

        # 验证最终版本
        final = await registry_dao.get_skill_container(skill.skill_id)
        assert final.metadata.get("version") == "1.0.5"
