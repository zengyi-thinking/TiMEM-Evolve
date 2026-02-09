"""LearnerService 单元测试

测试 LearnerService 的核心功能:
- 从反馈中学习（好评→技能，差评→规则）
- 从会话中学习（成功→技能，失败→规则）
- E.S.P 格式生成
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
import json

from timem_evolve.services.learner_service import LearnerService
from timem_evolve.models import Feedback, Session, Message, Skill, Rule, Workflow


class MockMessage:
    """模拟消息"""
    def __init__(self, role: str, content: str):
        self.role = role
        self.content = content


class MockSession:
    """模拟会话"""
    def __init__(self, session_id: str, task: str, messages: list, outcome: str = "success"):
        self.session_id = session_id
        self.task = task
        self.messages = messages
        self.outcome = outcome
        self.timestamp = datetime.now()

    def model_dump(self):
        return {
            "session_id": self.session_id,
            "task": self.task,
            "messages": [m.model_dump() for m in self.messages],
            "outcome": self.outcome,
            "timestamp": self.timestamp.isoformat()
        }


class MockFeedback:
    """模拟反馈"""
    def __init__(self, feedback_id: str, session_id: str, message_index: int,
                 rating: str, comment: str = None):
        self.feedback_id = feedback_id
        self.session_id = session_id
        self.message_index = message_index
        self.rating = rating
        self.comment = comment
        self.learned = False
        self.learned_skill_id = None
        self.learned_rule_id = None


class TestLearnerService:
    """LearnerService 测试类"""

    @pytest.fixture
    def mock_dao(self):
        """模拟 DAO"""
        dao = AsyncMock()
        dao.save_skill = AsyncMock()
        dao.save_rule = AsyncMock()
        dao.save_feedback = MagicMock()
        return dao

    @pytest.fixture
    def learner_service(self, mock_dao):
        """创建 LearnerService 实例（使用 mock LLM）"""
        with patch('timem_evolve.services.learner_service.create_chat_model') as mock_create:
            mock_llm = AsyncMock()
            mock_llm.ainvoke = AsyncMock()
            mock_create.return_value = mock_llm

            service = LearnerService(dao=mock_dao, model_name="test-model")
            service.llm = mock_llm
            return service

    # ========== _extract_dialog_turn 测试 ==========

    def test_extract_dialog_turn_basic(self, learner_service):
        """测试基本对话轮次提取"""
        messages = [
            MockMessage("user", "第一个问题"),
            MockMessage("assistant", "第一个回答"),
            MockMessage("user", "第二个问题"),
            MockMessage("assistant", "第二个回答"),
        ]

        result = learner_service._extract_dialog_turn(messages, 3)

        assert result["user_message"] == "第二个问题"
        assert result["ai_response"] == "第二个回答"
        assert "第一个问题" in result["context"]
        assert "第一个回答" in result["context"]

    def test_extract_dialog_turn_first_response(self, learner_service):
        """测试第一条回复的轮次提取"""
        messages = [
            MockMessage("user", "问题"),
            MockMessage("assistant", "回答"),
        ]

        result = learner_service._extract_dialog_turn(messages, 1)

        assert result["user_message"] == "问题"
        assert result["ai_response"] == "回答"
        assert result["context"] == "user: 问题"

    def test_extract_dialog_turn_invalid_index(self, learner_service):
        """测试无效索引"""
        messages = [MockMessage("user", "问题")]

        result = learner_service._extract_dialog_turn(messages, 0)
        # AI 回复需要前一条用户消息
        assert result["user_message"] == ""

    # ========== _format_messages 测试 ==========

    def test_format_messages_basic(self, learner_service):
        """测试消息格式化"""
        messages = [
            MockMessage("user", "你好"),
            MockMessage("assistant", "有什么可以帮你的？"),
        ]

        result = learner_service._format_messages(messages)

        assert "user: 你好" in result
        assert "assistant: 有什么可以帮你的？" in result

    def test_format_messages_empty(self, learner_service):
        """测试空消息列表"""
        result = learner_service._format_messages([])
        assert result == ""

    # ========== _infer_category 测试 ==========

    def test_infer_category_programming(self, learner_service):
        """测试编程相关分类推断"""
        assert learner_service._infer_category("代码解释", "") == "programming"  # 包含"代码"
        assert learner_service._infer_category("调试技巧", "") == "programming"  # 包含"调试"
        assert learner_service._infer_category("debug", "调试代码") == "programming"

    def test_infer_category_communication(self, learner_service):
        """测试沟通相关分类推断（不包含代码关键词）"""
        assert learner_service._infer_category("对话回复", "") == "communication"
        assert learner_service._infer_category("解释说明很清晰", "") == "communication"  # 不包含"代码"

    def test_infer_category_analysis(self, learner_service):
        """测试分析相关分类推断（不包含代码关键词）"""
        assert learner_service._infer_category("问题诊断", "") == "analysis"
        assert learner_service._infer_category("检查问题", "") == "analysis"  # 不包含"代码"

    def test_infer_category_other(self, learner_service):
        """测试其他分类推断"""
        assert learner_service._infer_category("未知技能", "") == "other"
        assert learner_service._infer_category("", "随机文本") == "other"

    # ========== _generate_decision_table_from_scenarios 测试 ==========

    def test_generate_decision_table_with_scenarios(self, learner_service):
        """测试带场景的决策表生成"""
        table = learner_service._generate_decision_table_from_scenarios(
            applicable="用户请求解释代码",
            not_applicable="用户请求编写代码"
        )

        assert len(table) == 2
        assert table[0]["action"] == "使用本技能"
        assert table[0]["priority"] == "高"
        assert table[1]["action"] == "不使用本技能 / 委托给其他技能"

    def test_generate_decision_table_empty(self, learner_service):
        """测试空场景的决策表生成"""
        table = learner_service._generate_decision_table_from_scenarios("", "")

        assert len(table) == 1
        assert table[0]["condition"] == "相关请求"
        assert table[0]["action"] == "使用本技能"

    def test_generate_decision_table_long_text(self, learner_service):
        """测试长文本场景的决策表生成（截断验证）"""
        long_applicable = "A" * 100
        table = learner_service._generate_decision_table_from_scenarios(
            applicable=long_applicable,
            not_applicable=""
        )

        assert len(table) == 1
        # 验证是否被截断（应该保留 ...）
        assert len(table[0]["condition"]) <= 53  # 50 + "..."

    # ========== learn_from_feedback 测试 ==========

    @pytest.mark.asyncio
    async def test_learn_from_positive_feedback_creates_skill(self, learner_service, mock_dao):
        """测试好评创建技能"""
        session = MockSession(
            session_id="session_001",
            task="解释代码",
            messages=[
                MockMessage("user", "请解释这段代码"),
                MockMessage("assistant", "这是快速排序算法...")
            ],
            outcome="success"
        )
        feedback = MockFeedback(
            feedback_id="feedback_001",
            session_id="session_001",
            message_index=1,
            rating="positive",
            comment="解释清晰"
        )

        # Mock LLM response
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "name": "代码解释技能",
            "description": "清晰解释代码逻辑",
            "category": "communication",
            "steps": ["理解代码", "分析结构", "组织语言"],
            "sop": "按照步骤逐步解释",
            "trigger_keywords": ["解释", "代码"],
            "confidence": 0.9
        })
        learner_service.llm.ainvoke = AsyncMock(return_value=mock_response)

        mock_dao.get_session = AsyncMock(return_value=session)

        result = await learner_service.learn_from_feedback(feedback)

        assert result is not None
        assert isinstance(result, str)  # skill_id
        mock_dao.save_skill.assert_called_once()
        assert feedback.learned == True
        assert feedback.learned_skill_id == result

    @pytest.mark.asyncio
    async def test_learn_from_negative_feedback_creates_rule(self, learner_service, mock_dao):
        """测试差评创建规则"""
        session = MockSession(
            session_id="session_002",
            task="解决问题",
            messages=[
                MockMessage("user", "程序崩溃了"),
                MockMessage("assistant", "可能是内存问题")
            ],
            outcome="failure"
        )
        feedback = MockFeedback(
            feedback_id="feedback_002",
            session_id="session_002",
            message_index=1,
            rating="negative",
            comment="诊断不全面"
        )

        # Mock LLM response
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "name": "诊断前收集信息",
            "description": "确保诊断前收集完整的错误信息",
            "constraint": "必须要求用户提供错误信息和复现步骤",
            "reason": "没有足够信息无法准确诊断问题",
            "confidence": 0.85
        })
        learner_service.llm.ainvoke = AsyncMock(return_value=mock_response)

        mock_dao.get_session = AsyncMock(return_value=session)

        result = await learner_service.learn_from_feedback(feedback)

        assert result is not None
        assert isinstance(result, str)  # rule_id
        mock_dao.save_rule.assert_called_once()
        assert feedback.learned == True
        assert feedback.learned_rule_id == result

    @pytest.mark.asyncio
    async def test_learn_from_feedback_session_not_found(self, learner_service, mock_dao):
        """测试会话不存在时返回 None"""
        mock_dao.get_session = AsyncMock(return_value=None)

        feedback = MockFeedback(
            feedback_id="feedback_003",
            session_id="nonexistent",
            message_index=0,
            rating="positive",
            comment="测试"
        )

        result = await learner_service.learn_from_feedback(feedback)

        assert result is None

    @pytest.mark.asyncio
    async def test_learn_from_feedback_invalid_message_index(self, learner_service, mock_dao):
        """测试无效消息索引"""
        session = MockSession(
            session_id="session_004",
            task="测试",
            messages=[MockMessage("user", "问题")],
            outcome="success"
        )
        mock_dao.get_session = AsyncMock(return_value=session)

        feedback = MockFeedback(
            feedback_id="feedback_004",
            session_id="session_004",
            message_index=5,  # 超出范围
            rating="positive",
            comment="测试"
        )

        result = await learner_service.learn_from_feedback(feedback)

        assert result is None

    # ========== LLM 响应解析测试 ==========

    @pytest.mark.asyncio
    async def test_extract_skill_with_json_code_block(self, learner_service, mock_dao):
        """测试带 JSON 代码块的技能提取"""
        session = MockSession(
            session_id="session_json_001",
            task="测试",
            messages=[
                MockMessage("user", "问题"),
                MockMessage("assistant", "回答")
            ],
            outcome="success"
        )
        feedback = MockFeedback(
            feedback_id="feedback_json_001",
            session_id="session_json_001",
            message_index=1,
            rating="positive",
            comment="好"
        )

        mock_response = MagicMock()
        mock_response.content = """```json
{
    "name": "测试技能",
    "description": "测试描述",
    "category": "communication",
    "steps": ["步骤1"],
    "sop": "测试流程",
    "trigger_keywords": ["测试"],
    "confidence": 0.8
}
```"""
        learner_service.llm.ainvoke = AsyncMock(return_value=mock_response)
        mock_dao.get_session = AsyncMock(return_value=session)

        result = await learner_service.learn_from_feedback(feedback)

        assert result is not None

    @pytest.mark.asyncio
    async def test_extract_skill_invalid_json(self, learner_service, mock_dao):
        """测试无效 JSON 时的处理"""
        session = MockSession(
            session_id="session_invalid_001",
            task="测试",
            messages=[
                MockMessage("user", "问题"),
                MockMessage("assistant", "回答")
            ],
            outcome="success"
        )
        feedback = MockFeedback(
            feedback_id="feedback_invalid_001",
            session_id="session_invalid_001",
            message_index=1,
            rating="positive",
            comment="好"
        )

        mock_response = MagicMock()
        mock_response.content = "这是无效的响应，不是 JSON"
        learner_service.llm.ainvoke = AsyncMock(return_value=mock_response)
        mock_dao.get_session = AsyncMock(return_value=session)

        result = await learner_service.learn_from_feedback(feedback)

        assert result is None  # 应该返回 None 而不是崩溃


class TestSkillExtraction:
    """技能提取测试类"""

    @pytest.fixture
    def mock_dao(self):
        dao = AsyncMock()
        dao.save_skill = AsyncMock()
        return dao

    @pytest.fixture
    def learner_service(self, mock_dao):
        with patch('timem_evolve.services.learner_service.create_chat_model') as mock_create:
            mock_llm = AsyncMock()
            mock_create.return_value = mock_llm

            service = LearnerService(dao=mock_dao, model_name="test-model")
            service.llm = mock_llm
            return service

    @pytest.mark.asyncio
    async def test_extract_skill_from_session(self, learner_service, mock_dao):
        """测试从会话中提取技能"""
        session = Session(
            session_id="session_extract_001",
            task="编写代码",
            messages=[
                Message(role="user", content="请写一个排序算法"),
                Message(role="assistant", content="以下是快速排序实现...")
            ],
            outcome="success"
        )

        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "name": "排序算法实现",
            "description": "快速排序算法的实现方法",
            "category": "programming",
            "steps": ["选择基准", "分区", "递归排序"],
            "sop": "标准快速排序流程",
            "trigger_keywords": ["排序", "算法"],
            "confidence": 0.9
        })
        learner_service.llm.ainvoke = AsyncMock(return_value=mock_response)

        result = await learner_service.extract_skill_from_session(session)

        assert result is not None
        assert result.name == "排序算法实现"
        mock_dao.save_skill.assert_called_once()


class TestRuleExtraction:
    """规则提取测试类"""

    @pytest.fixture
    def mock_dao(self):
        dao = AsyncMock()
        dao.save_rule = MagicMock()
        return dao

    @pytest.fixture
    def learner_service(self, mock_dao):
        with patch('timem_evolve.services.learner_service.create_chat_model') as mock_create:
            mock_llm = AsyncMock()
            mock_create.return_value = mock_llm

            service = LearnerService(dao=mock_dao, model_name="test-model")
            service.llm = mock_llm
            return service

    @pytest.mark.asyncio
    async def test_extract_rule_from_session(self, learner_service, mock_dao):
        """测试从失败会话中提取规则"""
        session = Session(
            session_id="session_rule_001",
            task="解决问题",
            messages=[
                Message(role="user", content="程序崩溃"),
                Message(role="assistant", content="建议重启")
            ],
            outcome="failure"
        )

        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "name": "重启前先诊断",
            "description": "解决问题前应先诊断根因",
            "constraint": "不要直接建议重启而忽略问题诊断",
            "reason": "重启只能暂时解决表面问题",
            "confidence": 0.8
        })
        learner_service.llm.ainvoke = AsyncMock(return_value=mock_response)

        result = await learner_service.extract_rule_from_session(session)

        assert result is not None
        assert result.name == "重启前先诊断"
        mock_dao.save_rule.assert_called_once()
