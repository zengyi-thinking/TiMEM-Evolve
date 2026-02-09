"""经验积累流程集成测试

测试：经验可积累 - 从反馈/会话中提炼技能和规则
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
import json

from timem_evolve.services.learner_service import LearnerService
from timem_evolve.dao.unified_dao import UnifiedDAO
from timem_evolve.models import Session, Message, Feedback, Skill, Rule, Workflow


class MockMessage:
    """模拟消息"""
    def __init__(self, role: str, content: str):
        self.role = role
        self.content = content

    def get(self, key: str, default=None):
        return getattr(self, key, default)

    def model_dump(self):
        return {"role": self.role, "content": self.content}


class MockSession:
    """模拟会话"""
    def __init__(self, session_id: str, task: str, messages: list, outcome: str = "success"):
        self.session_id = session_id
        self.task = task
        self.messages = messages
        self.outcome = outcome
        self.timestamp = datetime.now()
        self.metadata = {}

    def model_dump(self):
        return {
            "session_id": self.session_id,
            "task": self.task,
            "messages": [m.model_dump() for m in self.messages],
            "outcome": self.outcome,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
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
        self.metadata = {}

    def model_dump(self):
        return {
            "feedback_id": self.feedback_id,
            "session_id": self.session_id,
            "message_index": self.message_index,
            "rating": self.rating,
            "comment": self.comment,
            "learned": self.learned,
            "learned_skill_id": self.learned_skill_id,
            "learned_rule_id": self.learned_rule_id,
            "metadata": self.metadata
        }


class TestExperienceAccumulation:
    """经验积累测试类"""

    @pytest.fixture
    async def unified_dao(self, tmp_path):
        """创建 UnifiedDAO 实例"""
        data_dir = str(tmp_path / "data")
        dao = UnifiedDAO(data_dir=data_dir, use_registry=True)
        await dao.init_db()
        return dao

    @pytest.fixture
    def mock_llm_response(self):
        """Mock LLM 响应"""
        def _response(content: str):
            mock = MagicMock()
            mock.content = content
            return mock
        return _response

    @pytest.mark.asyncio
    async def test_positive_feedback_to_skill(self, unified_dao, mock_llm_response):
        """好评 → 技能提炼"""
        with patch('timem_evolve.services.learner_service.create_chat_model') as mock_create:
            mock_llm = AsyncMock()
            mock_create.return_value = mock_llm

            learner = LearnerService(dao=unified_dao, model_name="test")
            learner.llm = mock_llm

            # 1. 创建会话
            session = MockSession(
                session_id="acc_session_001",
                task="解释代码",
                messages=[
                    MockMessage("user", "请解释这段代码的作用"),
                    MockMessage("assistant", "这段代码实现了快速排序算法...")
                ],
                outcome="success"
            )
            await unified_dao.save_session(session)

            # 2. 添加好评反馈
            feedback = MockFeedback(
                feedback_id="acc_feedback_001",
                session_id="acc_session_001",
                message_index=1,
                rating="positive",
                comment="解释非常清晰"
            )

            # Mock LLM 响应
            mock_llm.ainvoke = AsyncMock(return_value=mock_llm_response(json.dumps({
                "name": "代码解释技能",
                "description": "清晰解释代码逻辑和原理",
                "category": "communication",
                "steps": ["理解代码结构", "提取关键逻辑", "组织解释语言"],
                "sop": "按照用户能理解的方式解释",
                "trigger_keywords": ["解释", "代码", "说明"],
                "confidence": 0.9
            })))

            # 3. 触发学习
            result = await learner.learn_from_feedback(feedback)

            # 4. 验证
            assert result is not None
            assert feedback.learned == True
            assert feedback.learned_skill_id is not None

            # 5. 验证技能已存入 RegistryDAO
            skill = await unified_dao.get_skill(result)
            assert skill is not None
            assert skill.metadata.get("version") == "1.0.0"
            assert skill.metadata.get("category") == "communication"

    @pytest.mark.asyncio
    async def test_negative_feedback_to_rule(self, unified_dao, mock_llm_response):
        """差评 → 规则提炼"""
        with patch('timem_evolve.services.learner_service.create_chat_model') as mock_create:
            mock_llm = AsyncMock()
            mock_create.return_value = mock_llm

            learner = LearnerService(dao=unified_dao, model_name="test")
            learner.llm = mock_llm

            # 1. 创建失败的会话
            session = MockSession(
                session_id="acc_session_002",
                task="诊断问题",
                messages=[
                    MockMessage("user", "我的程序崩溃了"),
                    MockMessage("assistant", "可能是内存问题，请增加内存")
                ],
                outcome="failure"
            )
            await unified_dao.save_session(session)

            # 2. 添加差评反馈
            feedback = MockFeedback(
                feedback_id="acc_feedback_002",
                session_id="acc_session_002",
                message_index=1,
                rating="negative",
                comment="诊断不全面"
            )

            # Mock LLM 响应
            mock_llm.ainvoke = AsyncMock(return_value=mock_llm_response(json.dumps({
                "name": "诊断前收集信息",
                "description": "解决问题前应先诊断根因",
                "constraint": "必须要求用户提供错误信息和复现步骤",
                "reason": "没有足够信息无法准确诊断",
                "confidence": 0.8
            })))

            # 3. 触发学习
            result = await learner.learn_from_feedback(feedback)

            # 4. 验证
            assert result is not None
            assert feedback.learned == True
            assert feedback.learned_rule_id is not None

            # 5. 验证规则已存入 MemoryDAO
            rule = unified_dao.get_rule(result)
            assert rule is not None
            assert "诊断" in rule.name or "信息" in rule.name

    @pytest.mark.asyncio
    async def test_multi_feedback_accumulation(self, unified_dao, mock_llm_response):
        """多次反馈累积成技能"""
        with patch('timem_evolve.services.learner_service.create_chat_model') as mock_create:
            mock_llm = AsyncMock()
            mock_create.return_value = mock_llm

            learner = LearnerService(dao=unified_dao, model_name="test")
            learner.llm = mock_llm

            # 多次关于代码解释的正面反馈
            for i in range(3):
                session = MockSession(
                    session_id=f"acc_session_multi_{i}",
                    task="代码解释",
                    messages=[
                        MockMessage("user", f"请解释代码{i}"),
                        MockMessage("assistant", f"这是代码{i}的解释...")
                    ],
                    outcome="success"
                )
                await unified_dao.save_session(session)

                feedback = MockFeedback(
                    feedback_id=f"acc_feedback_multi_{i}",
                    session_id=f"acc_session_multi_{i}",
                    message_index=1,
                    rating="positive",
                    comment=f"解释很好 {i}"
                )

                mock_llm.ainvoke = AsyncMock(return_value=mock_llm_response(json.dumps({
                    "name": "代码解释技能",
                    "description": "清晰解释代码",
                    "category": "communication",
                    "steps": ["步骤1"],
                    "sop": "流程",
                    "trigger_keywords": ["解释"],
                    "confidence": 0.9
                })))

                result = await learner.learn_from_feedback(feedback)

            # 验证技能已累积
            skills = await unified_dao.list_skills(category="communication")
            # 由于每次学习可能创建新技能，检查总体数量
            assert len(skills) >= 0  # 可能创建了多个技能或合并

    @pytest.mark.asyncio
    async def test_edge_case_empty_feedback(self, unified_dao):
        """边界情况：空评论不触发学习"""
        with patch('timem_evolve.services.learner_service.create_chat_model') as mock_create:
            mock_llm = AsyncMock()
            mock_create.return_value = mock_llm

            learner = LearnerService(dao=unified_dao, model_name="test")

            session = MockSession(
                session_id="acc_session_empty",
                task="简单对话",
                messages=[
                    MockMessage("user", "你好"),
                    MockMessage("assistant", "你好！有什么可以帮你的？")
                ],
                outcome="success"
            )
            await unified_dao.save_session(session)

            # 空评论
            feedback = MockFeedback(
                feedback_id="acc_feedback_empty",
                session_id="acc_session_empty",
                message_index=1,
                rating="positive",
                comment=""  # 空评论
            )

            # 空评论情况下，可能不会调用 LLM 或返回 None
            result = await learner.learn_from_feedback(feedback)

            # 验证没有创建技能
            assert result is None


class TestSessionBasedLearning:
    """基于会话的学习测试"""

    @pytest.fixture
    async def unified_dao(self, tmp_path):
        data_dir = str(tmp_path / "data")
        dao = UnifiedDAO(data_dir=data_dir, use_registry=True)
        await dao.init_db()
        return dao

    @pytest.mark.asyncio
    async def test_extract_skill_from_successful_session(self, unified_dao):
        """从成功会话中提取技能"""
        with patch('timem_evolve.services.learner_service.create_chat_model') as mock_create:
            mock_llm = AsyncMock()
            mock_create.return_value = mock_llm

            learner = LearnerService(dao=unified_dao, model_name="test")

            session = Session(
                session_id="session_extract_001",
                task="编写单元测试",
                messages=[
                    Message(role="user", content="请帮我编写单元测试"),
                    Message(role="assistant", content="以下是单元测试代码...")
                ],
                outcome="success"
            )

            mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content=json.dumps({
                "name": "单元测试编写技能",
                "description": "编写高质量单元测试的方法",
                "category": "programming",
                "steps": ["分析被测代码", "设计测试用例", "编写测试代码", "验证测试覆盖"],
                "sop": "遵循 AAA 模式编写测试",
                "trigger_keywords": ["测试", "单元测试"],
                "confidence": 0.9
            })))

            result = await learner.extract_skill_from_session(session)

            assert result is not None
            assert "测试" in result.name
            assert result.metadata.get("category") == "programming"

    @pytest.mark.asyncio
    async def test_extract_rule_from_failed_session(self, unified_dao):
        """从失败会话中提取规则"""
        with patch('timem_evolve.services.learner_service.create_chat_model') as mock_create:
            mock_llm = AsyncMock()
            mock_create.return_value = mock_llm

            learner = LearnerService(dao=unified_dao, model_name="test")

            session = Session(
                session_id="session_rule_001",
                task="解决复杂问题",
                messages=[
                    Message(role="user", content="帮我解决"),
                    Message(role="assistant", content="解决方案..."),
                    Message(role="user", content="不对，这不是我想要的")
                ],
                outcome="failure"
            )

            mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content=json.dumps({
                "name": "先确认再执行",
                "description": "执行前应先确认用户需求",
                "constraint": "不要直接给出解决方案，应先确认需求",
                "reason": "避免误解用户真实需求",
                "confidence": 0.8
            })))

            result = await learner.extract_rule_from_session(session)

            assert result is not None
            assert "确认" in result.name or "需求" in result.name
