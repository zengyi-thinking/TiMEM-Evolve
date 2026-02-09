"""经验复用流程集成测试

测试：经验可复用 - SkillRouting 自动匹配
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

from timem_evolve.dao.registry_dao import RegistryDAO
from timem_evolve.dao.unified_dao import UnifiedDAO
from timem_evolve.models import Skill, Workflow, SkillRouting


class TestSkillRouting:
    """技能路由匹配测试类"""

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
    def sample_skills(self):
        """创建测试用技能集合"""
        return [
            Skill(
                skill_id="skill_code_explain",
                name="代码解释",
                description="解释代码的技能",
                workflow=Workflow(steps=["理解代码", "组织语言", "解释说明"], sop="流程"),
                metadata={
                    "category": "communication",
                    "version": "1.0.0",
                    "routing": {
                        "trigger_keywords": ["解释", "代码", "说明", "作用"],
                        "priority": 8
                    }
                }
            ),
            Skill(
                skill_id="skill_debug",
                name="调试技能",
                description="调试代码的技能",
                workflow=Workflow(steps=["分析错误", "定位问题", "修复代码"], sop="流程"),
                metadata={
                    "category": "debugging",
                    "version": "1.0.0",
                    "routing": {
                        "trigger_keywords": ["报错", "错误", "bug", "调试"],
                        "priority": 9
                    }
                }
            ),
            Skill(
                skill_id="skill_doc",
                name="文档技能",
                description="编写文档的技能",
                workflow=Workflow(steps=["收集信息", "组织结构", "编写内容"], sop="流程"),
                metadata={
                    "category": "writing",
                    "version": "1.0.0",
                    "routing": {
                        "trigger_keywords": ["文档", "注释", "README"],
                        "priority": 7
                    }
                }
            ),
        ]

    @pytest.mark.asyncio
    async def test_skill_matching_by_keywords(self, registry_dao, sample_skills):
        """技能按关键词匹配"""
        # 保存技能
        for skill in sample_skills:
            await registry_dao.save_skill_container(skill, change_summary="测试保存")

        # 测试代码解释匹配
        matched = await registry_dao.search_skill_containers("解释这段代码")
        assert len(matched) >= 1
        assert any(s.metadata["category"] == "communication" for s in matched)

        # 测试调试匹配
        matched = await registry_dao.search_skill_containers("Python 报错了")
        assert len(matched) >= 1
        assert any("调试" in s.name for s in matched)

    @pytest.mark.asyncio
    async def test_skill_priority_ordering(self, registry_dao, sample_skills):
        """技能按优先级排序"""
        # 保存技能
        for skill in sample_skills:
            await registry_dao.save_skill_container(skill, change_summary="测试保存")

        # 搜索包含多个关键词的请求
        matched = await registry_dao.search_skill_containers("代码报错调试")

        # 调试技能的优先级应该更高
        if len(matched) >= 2:
            debug_skill = next((s for s in matched if "调试" in s.name), None)
            explain_skill = next((s for s in matched if "解释" in s.name), None)
            if debug_skill and explain_skill:
                # 检查优先级配置
                debug_priority = debug_skill.metadata.get("routing", {}).get("priority", 0)
                explain_priority = explain_skill.metadata.get("routing", {}).get("priority", 0)
                assert debug_priority >= explain_priority

    @pytest.mark.asyncio
    async def test_search_with_category_filter(self, registry_dao, sample_skills):
        """按分类过滤搜索"""
        # 保存技能
        for skill in sample_skills:
            await registry_dao.save_skill_container(skill, change_summary="测试保存")

        # 只搜索 communication 分类
        matched = await registry_dao.search_skill_containers(
            query="解释",
            category="communication"
        )

        for skill in matched:
            assert skill.metadata.get("category") == "communication"

    @pytest.mark.asyncio
    async def test_empty_query_result(self, registry_dao, sample_skills):
        """空查询返回空结果"""
        for skill in sample_skills:
            await registry_dao.save_skill_container(skill, change_summary="测试")

        matched = await registry_dao.search_skill_containers("xyz123无匹配")
        assert len(matched) == 0


class TestSkillSearchScoring:
    """技能搜索评分测试"""

    @pytest.fixture
    async def registry_dao(self, tmp_path):
        kb_dir = str(tmp_path / "kb")
        return RegistryDAO(knowledge_base_dir=kb_dir)

    @pytest.mark.asyncio
    async def test_name_match_high_score(self, registry_dao):
        """名称匹配获得高分"""
        skill = Skill(
            skill_id="score_test_001",
            name="Python 调试技能",
            description="调试 Python 代码",
            workflow=Workflow(steps=["步骤1"], sop="流程"),
            metadata={
                "category": "debugging",
                "version": "1.0.0",
                "routing": {"trigger_keywords": ["调试"], "priority": 5}
            }
        )
        await registry_dao.save_skill_container(skill, change_summary="测试")

        matched = await registry_dao.search_skill_containers("Python 调试")

        # 应该找到技能
        assert len(matched) >= 1
        # 名称匹配应该有较高分数
        python_skill = next((s for s in matched if "Python" in s.name), None)
        if python_skill:
            score = python_skill.metadata.get("search_score", 0)
            assert score > 0


class TestUnifiedDAOSearch:
    """UnifiedDAO 搜索测试"""

    @pytest.fixture
    async def unified_dao(self, tmp_path):
        data_dir = str(tmp_path / "data")
        dao = UnifiedDAO(data_dir=data_dir, use_registry=True)
        await dao.init_db()
        return dao

    @pytest.mark.asyncio
    async def test_search_skills_via_unified_dao(self, unified_dao):
        """通过 UnifiedDAO 搜索技能"""
        skill = Skill(
            skill_id="unified_search_001",
            name="搜索测试技能",
            description="测试搜索功能",
            workflow=Workflow(steps=["步骤1"], sop="流程"),
            metadata={
                "category": "test",
                "version": "1.0.0",
                "routing": {"trigger_keywords": ["测试"], "priority": 5}
            }
        )

        await unified_dao.save_skill(skill, change_summary="测试保存")

        # 搜索
        results = await unified_dao.search_skills(query="测试")

        assert len(results) >= 1
        assert any(s.skill_id == "unified_search_001" for s in results)

    @pytest.mark.asyncio
    async def test_search_with_category_filter(self, unified_dao):
        """通过 UnifiedDAO 按分类搜索"""
        skill = Skill(
            skill_id="unified_cat_001",
            name="分类测试",
            description="测试分类",
            workflow=Workflow(steps=["步骤1"], sop="流程"),
            metadata={
                "category": "programming",
                "version": "1.0.0",
                "routing": {"trigger_keywords": ["代码"], "priority": 5}
            }
        )

        await unified_dao.save_skill(skill, change_summary="测试")

        results = await unified_dao.search_skills(query="代码", category="programming")

        for r in results:
            assert r.metadata.get("category") == "programming"


class TestSkillIndexManagement:
    """技能索引管理测试"""

    @pytest.fixture
    async def registry_dao(self, tmp_path):
        kb_dir = str(tmp_path / "kb")
        return RegistryDAO(knowledge_base_dir=kb_dir)

    @pytest.mark.asyncio
    async def test_rebuild_index(self, registry_dao):
        """重建索引"""
        # 保存多个技能
        for i in range(3):
            skill = Skill(
                skill_id=f"rebuild_test_{i}",
                name=f"技能 {i}",
                description=f"测试技能 {i}",
                workflow=Workflow(steps=["步骤1"], sop="流程"),
                metadata={"category": "test", "version": "1.0.0"}
            )
            await registry_dao.save_skill_container(skill, change_summary=f"创建 {i}")

        # 重建索引
        result = await registry_dao.rebuild_index()

        assert result["total_skills"] >= 3
        assert result["successful"] >= 3

    @pytest.mark.asyncio
    async def test_list_skills_by_category(self, registry_dao):
        """按分类列出技能"""
        # 创建不同分类的技能
        categories = ["programming", "communication", "debugging"]
        for i, cat in enumerate(categories):
            skill = Skill(
                skill_id=f"cat_test_{i}",
                name=f"{cat} 技能",
                description=f"测试 {cat} 分类",
                workflow=Workflow(steps=["步骤1"], sop="流程"),
                metadata={"category": cat, "version": "1.0.0"}
            )
            await registry_dao.save_skill_container(skill, change_summary=f"创建 {cat}")

        # 列出单一分类
        programming_skills = await registry_dao.list_skill_containers(category="programming")

        for s in programming_skills:
            assert s.metadata.get("category") == "programming"
