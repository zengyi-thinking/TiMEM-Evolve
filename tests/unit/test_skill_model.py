"""Skill 模型单元测试

测试技能数据模型的功能和 E.S.P 方法。
"""
import pytest
from datetime import datetime

from timem_evolve.models import Skill, Workflow, SkillRouting


class TestWorkflow:
    """工作流程模型测试"""

    def test_workflow_creation(self):
        """测试工作流程创建"""
        workflow = Workflow(
            steps=["步骤1", "步骤2", "步骤3"],
            sop="标准操作流程"
        )

        assert len(workflow.steps) == 3
        assert workflow.sop == "标准操作流程"

    def test_workflow_default(self):
        """测试工作流程默认值"""
        workflow = Workflow()

        assert workflow.steps == []
        assert workflow.sop == ""


class TestSkillRouting:
    """技能路由模型测试"""

    def test_skill_routing_creation(self):
        """测试路由创建"""
        routing = SkillRouting(
            trigger_keywords=["测试", "检查"],
            priority=8,
            conditions=["context == 'test'"]
        )

        assert routing.trigger_keywords == ["测试", "检查"]
        assert routing.priority == 8
        assert routing.conditions == ["context == 'test'"]

    def test_skill_routing_default(self):
        """测试路由默认值"""
        routing = SkillRouting()

        assert routing.trigger_keywords == []
        assert routing.priority == 5
        assert routing.conditions == []


class TestSkill:
    """技能模型测试"""

    def test_skill_creation(self):
        """测试技能创建"""
        skill = Skill(
            skill_id="test_001",
            name="测试技能",
            description="这是一个测试技能"
        )

        assert skill.skill_id == "test_001"
        assert skill.name == "测试技能"
        assert skill.description == "这是一个测试技能"

    def test_skill_with_workflow(self):
        """测试带工作流程的技能"""
        workflow = Workflow(
            steps=["步骤1", "步骤2"],
            sop="标准流程"
        )

        skill = Skill(
            skill_id="test_002",
            name="带流程的技能",
            description="测试",
            workflow=workflow
        )

        assert len(skill.workflow.steps) == 2

    def test_skill_default_values(self):
        """测试技能默认值"""
        skill = Skill(
            name="测试",
            description="测试"
        )

        assert skill.skill_id is not None  # UUID
        assert skill.source_sessions == []
        assert skill.confidence == 0.5
        assert skill.metadata == {}

    def test_skill_timestamps(self):
        """测试时间戳"""
        before = datetime.now()

        skill = Skill(
            name="测试",
            description="测试"
        )

        after = datetime.now()

        assert skill.created_at >= before
        assert skill.created_at <= after
        assert skill.updated_at >= before
        assert skill.updated_at <= after


class TestSkillProperties:
    """技能属性测试"""

    def test_category_property(self, sample_skill):
        """测试 category 属性"""
        assert sample_skill.category == "test"

    def test_category_default(self):
        """测试默认 category"""
        skill = Skill(name="测试", description="测试")
        assert skill.category == "uncategorized"

    def test_version_property(self, sample_skill):
        """测试 version 属性"""
        assert sample_skill.version == "1.0.0"

    def test_version_default(self):
        """测试默认 version"""
        skill = Skill(name="测试", description="测试")
        assert skill.version == "1.0.0"

    def test_tags_property(self, sample_skill):
        """测试 tags 属性"""
        assert "测试" in sample_skill.tags
        assert "单元测试" in sample_skill.tags

    def test_tags_default(self):
        """测试默认 tags"""
        skill = Skill(name="测试", description="测试")
        assert skill.tags == []

    def test_routing_property(self, sample_skill):
        """测试 routing 属性"""
        routing = sample_skill.routing

        assert isinstance(routing, SkillRouting)
        assert routing.priority == 5  # 默认值


class TestSkillMetadata:
    """技能元数据测试"""

    def test_metadata_access(self, sample_skill):
        """测试元数据访问"""
        assert sample_skill.metadata["category"] == "test"
        assert sample_skill.metadata["version"] == "1.0.0"

    def test_metadata_modification(self, sample_skill):
        """测试元数据修改"""
        sample_skill.metadata["new_field"] = "new_value"

        assert sample_skill.metadata["new_field"] == "new_value"

    def test_metadata_decision_table(self, sample_skill):
        """测试决策表"""
        decision_table = sample_skill.metadata.get("decision_table", [])

        assert len(decision_table) == 1
        assert decision_table[0]["condition"] == "测试条件 A"

    def test_metadata_rules(self, sample_skill):
        """测试规则"""
        must_do = sample_skill.metadata.get("rules_must_do", [])
        dont = sample_skill.metadata.get("rules_dont", [])

        assert "必须验证每一步结果" in must_do
        assert "不能跳过任何步骤" in dont


class TestSkillSerialization:
    """技能序列化测试"""

    def test_skill_to_dict(self, sample_skill):
        """测试转换为字典"""
        data = sample_skill.model_dump()

        assert data["skill_id"] == sample_skill.skill_id
        assert data["name"] == sample_skill.name
        assert data["description"] == sample_skill.description

    def test_skill_from_dict(self):
        """测试从字典创建"""
        data = {
            "skill_id": "test_001",
            "name": "测试技能",
            "description": "测试",
            "workflow": {
                "steps": ["步骤1"],
                "sop": "流程"
            },
            "source_sessions": [],
            "confidence": 0.9,
            "metadata": {}
        }

        skill = Skill(**data)

        assert skill.skill_id == "test_001"
        assert skill.name == "测试技能"

    def test_skill_json_serialization(self, sample_skill):
        """测试 JSON 序列化"""
        import json

        json_str = sample_skill.model_dump_json()
        data = json.loads(json_str)

        assert data["skill_id"] == sample_skill.skill_id
        assert data["name"] == sample_skill.name

    def test_skill_with_datetime_serialization(self, sample_skill):
        """测试带时间戳的序列化"""
        import json

        json_str = sample_skill.model_dump_json()
        data = json.loads(json_str)

        # datetime 应该被序列化为 ISO 格式字符串
        assert "created_at" in data
        assert "updated_at" in data
