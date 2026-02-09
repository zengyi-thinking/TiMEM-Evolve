"""CoachService 单元测试

测试 CoachService 的核心功能:
- 任务生成
- 任务执行
- 评估与反馈
- 学习追踪
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
import json
from pathlib import Path

from timem_evolve.services.coach_service import CoachService, CoachStorage
from timem_evolve.models import CoachTask, Rule


class TestCoachStorage:
    """CoachStorage 测试类"""

    @pytest.fixture
    def coach_storage(self, tmp_path):
        """创建 CoachStorage 实例（使用临时目录）"""
        return CoachStorage(data_dir=str(tmp_path))

    def test_storage_initialization(self, coach_storage):
        """测试存储初始化"""
        assert coach_storage.tasks_path.exists()

    def test_save_and_load_task(self, coach_storage):
        """测试保存和加载任务"""
        task = CoachTask(
            task_id="test_task_001",
            business_goal="提高代码质量",
            task_description="编写单元测试",
            difficulty="medium",
            status="pending"
        )

        coach_storage.save_task(task)

        loaded = coach_storage.list_tasks()
        assert len(loaded) == 1
        assert loaded[0].task_id == "test_task_001"

    def test_update_existing_task(self, coach_storage):
        """测试更新已存在的任务"""
        task = CoachTask(
            task_id="test_task_002",
            business_goal="提高代码质量",
            task_description="编写单元测试",
            difficulty="medium",
            status="pending"
        )

        coach_storage.save_task(task)

        # 更新任务
        task.status = "completed"
        coach_storage.save_task(task)

        loaded = coach_storage.list_tasks()
        assert len(loaded) == 1
        assert loaded[0].status == "completed"

    def test_list_tasks_by_status(self, coach_storage):
        """测试按状态过滤任务"""
        tasks = [
            CoachTask(task_id="t1", business_goal="g1", task_description="d1", difficulty="easy", status="pending"),
            CoachTask(task_id="t2", business_goal="g2", task_description="d2", difficulty="medium", status="completed"),
            CoachTask(task_id="t3", business_goal="g3", task_description="d3", difficulty="hard", status="running"),
        ]

        for task in tasks:
            coach_storage.save_task(task)

        pending = coach_storage.list_tasks(status="pending")
        completed = coach_storage.list_tasks(status="completed")

        assert len(pending) == 1
        assert pending[0].task_id == "t1"
        assert len(completed) == 1
        assert completed[0].task_id == "t2"

    def test_list_all_tasks(self, coach_storage):
        """测试列出所有任务"""
        tasks = [
            CoachTask(task_id="t1", business_goal="g1", task_description="d1", difficulty="easy", status="pending"),
            CoachTask(task_id="t2", business_goal="g2", task_description="d2", difficulty="medium", status="completed"),
        ]

        for task in tasks:
            coach_storage.save_task(task)

        all_tasks = coach_storage.list_tasks()
        assert len(all_tasks) == 2


class TestCoachServiceBasics:
    """CoachService 基础功能测试"""

    @pytest.fixture
    def mock_dao(self, tmp_path):
        """模拟 DAO"""
        dao = MagicMock()
        dao.data_dir = str(tmp_path)
        dao.save_session = AsyncMock()
        dao.get_session = AsyncMock()
        return dao

    @pytest.fixture
    def mock_learner_service(self):
        """模拟 LearnerService"""
        learner = MagicMock()
        learner.extract_skill_from_session = AsyncMock(return_value=None)
        learner.extract_rule_from_session = AsyncMock(return_value=None)
        return learner

    @pytest.fixture
    def coach_service(self, mock_dao, mock_learner_service):
        """创建 CoachService 实例（使用 mock LLM）"""
        with patch('timem_evolve.services.coach_service.create_chat_model') as mock_create:
            mock_llm = AsyncMock()
            mock_llm.ainvoke = AsyncMock()
            mock_create.return_value = mock_llm

            service = CoachService(
                dao=mock_dao,
                learner_service=mock_learner_service,
                model_name="test-model"
            )
            service.llm = mock_llm
            return service

    @pytest.mark.asyncio
    async def test_generate_task_success(self, coach_service):
        """测试成功生成任务"""
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "task_description": "编写一个 Python 函数实现快速排序",
            "difficulty": "medium"
        })
        coach_service.llm.ainvoke = AsyncMock(return_value=mock_response)

        result = await coach_service.generate_task("提高编程能力")

        assert result is not None
        assert isinstance(result, CoachTask)
        assert result.business_goal == "提高编程能力"
        assert result.status == "pending"
        assert result.task_description is not None

    @pytest.mark.asyncio
    async def test_generate_task_with_json_code_block(self, coach_service):
        """测试带 JSON 代码块的任务生成"""
        mock_response = MagicMock()
        mock_response.content = """```json
{
    "task_description": "实现一个 HTTP 请求工具",
    "difficulty": "easy"
}
```"""
        coach_service.llm.ainvoke = AsyncMock(return_value=mock_response)

        result = await coach_service.generate_task("学习网络编程")

        assert result is not None
        assert "HTTP" in result.task_description


class TestCoachStateTracking:
    """Coach 状态追踪测试"""

    @pytest.fixture
    def coach_service(self, tmp_path):
        """创建 CoachService 实例"""
        mock_dao = MagicMock()
        mock_dao.data_dir = str(tmp_path)

        mock_learner = MagicMock()
        mock_learner.extract_skill_from_session = AsyncMock(return_value=None)
        mock_learner.extract_rule_from_session = AsyncMock(return_value=None)

        with patch('timem_evolve.services.coach_service.create_chat_model') as mock_create:
            mock_llm = AsyncMock()
            mock_create.return_value = mock_llm

            service = CoachService(
                dao=mock_dao,
                learner_service=mock_learner,
                model_name="test"
            )
            return service

    def test_initial_state(self, coach_service):
        """初始状态"""
        state = coach_service.get_state()

        assert state.total_tasks == 0
        assert state.completed_tasks == 0
        assert state.successful_tasks == 0
        assert state.failed_tasks == 0
        assert state.skills_gained == 0
        assert state.rules_gained == 0

    def test_state_after_completed_tasks(self, coach_service):
        """完成任务后状态"""
        # 模拟完成任务
        tasks = [
            CoachTask(task_id="s1", business_goal="g1", task_description="d1", difficulty="easy",
                     status="completed", outcome="success", learned_skill_id="skill1"),
            CoachTask(task_id="s2", business_goal="g2", task_description="d2", difficulty="medium",
                     status="completed", outcome="success", learned_skill_id="skill2"),
            CoachTask(task_id="s3", business_goal="g3", task_description="d3", difficulty="hard",
                     status="completed", outcome="failure", learned_rule_id="rule1"),
        ]

        for task in tasks:
            coach_service.coach_storage.save_task(task)

        state = coach_service.get_state()

        assert state.total_tasks == 3
        assert state.completed_tasks == 3
        assert state.successful_tasks == 2
        assert state.failed_tasks == 1
        assert state.skills_gained == 2
        assert state.rules_gained == 1


class TestCoachTaskPersistence:
    """Coach 任务持久化测试"""

    @pytest.fixture
    def coach_service(self, tmp_path):
        """创建 CoachService 实例"""
        mock_dao = MagicMock()
        mock_dao.data_dir = str(tmp_path)

        mock_learner = MagicMock()

        with patch('timem_evolve.services.coach_service.create_chat_model') as mock_create:
            mock_llm = AsyncMock()
            mock_create.return_value = mock_llm

            return CoachService(
                dao=mock_dao,
                learner_service=mock_learner,
                model_name="test"
            )

    def test_task_persistence(self, coach_service):
        """任务持久化"""
        task = CoachTask(
            task_id="persist_test_001",
            business_goal="测试持久化",
            task_description="测试任务",
            difficulty="easy",
            status="completed",
            outcome="success",
            coach_feedback="做得很好",
            session_id="session_001",
            learned_skill_id="skill_001"
        )

        coach_service.coach_storage.save_task(task)

        # 重新加载
        loaded = coach_service.coach_storage.list_tasks()
        assert len(loaded) == 1
        assert loaded[0].task_id == "persist_test_001"
        assert loaded[0].coach_feedback == "做得很好"


class TestCoachMultipleGoals:
    """Coach 多目标测试"""

    @pytest.fixture
    def coach_service(self, tmp_path):
        """创建 CoachService 实例"""
        mock_dao = MagicMock()
        mock_dao.data_dir = str(tmp_path)

        mock_learner = MagicMock()

        with patch('timem_evolve.services.coach_service.create_chat_model') as mock_create:
            mock_llm = AsyncMock()
            mock_create.return_value = mock_llm

            return CoachService(
                dao=mock_dao,
                learner_service=mock_learner,
                model_name="test"
            )

    @pytest.mark.asyncio
    async def test_different_business_goals(self, coach_service):
        """不同业务目标生成不同任务"""
        goals = [
            "提高编程能力",
            "改善沟通技巧",
            "增强问题分析能力",
        ]

        for goal in goals:
            # Mock 响应
            mock_response = MagicMock()
            mock_response.content = json.dumps({
                "task_description": f"关于{goal}的具体任务",
                "difficulty": "medium"
            })
            coach_service.llm.ainvoke = AsyncMock(return_value=mock_response)

            task = await coach_service.generate_task(goal)

            assert task.business_goal == goal
            assert task.task_description is not None
            assert task.difficulty in ["easy", "medium", "hard"]
