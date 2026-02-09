"""Coach 端到端测试

测试：Coach 模块完整工作流
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
import json

from timem_evolve.services.coach_service import CoachService, CoachStorage
from timem_evolve.services.learner_service import LearnerService
from timem_evolve.dao.memory_dao import MemoryDAO
from timem_evolve.models import CoachTask


class TestCoachEndToEnd:
    """Coach 端到端测试类"""

    def test_coach_generate_task_basic(self, tmp_path):
        """测试 Coach 生成任务（基础测试）"""
        # 直接创建 Mock LLM
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "task_description": "编写一个 Python 函数，实现斐波那契数列",
            "difficulty": "easy"
        })
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        # 创建 MemoryDAO 和 mock learner
        temp_dir = str(tmp_path / "coach_test")
        memory_dao = MemoryDAO(data_dir=temp_dir)
        mock_learner = MagicMock()
        mock_learner.extract_skill_from_session = AsyncMock(return_value=None)
        mock_learner.extract_rule_from_session = AsyncMock(return_value=None)

        # 补丁 create_chat_model
        with patch('timem_evolve.services.coach_service.create_chat_model', return_value=mock_llm):
            service = CoachService(
                dao=memory_dao,
                learner_service=mock_learner,
                model_name="test"
            )
            service.llm = mock_llm

        # 生成任务
        import asyncio
        task = asyncio.get_event_loop().run_until_complete(
            service.generate_task("提高编程能力")
        )

        assert task.status == "pending"
        assert task.task_description is not None
        assert "斐波那契" in task.task_description or "Python" in task.task_description

    def test_coach_state_tracking(self, tmp_path):
        """测试 Coach 状态追踪"""
        temp_dir = str(tmp_path / "coach_state")

        # 先创建目录
        import os
        os.makedirs(temp_dir, exist_ok=True)

        storage = CoachStorage(data_dir=temp_dir)

        # 初始状态
        state = storage.get_state()
        assert state.total_tasks == 0

        # 保存任务
        task = CoachTask(
            task_id="test_001",
            business_goal="测试目标",
            task_description="测试任务",
            difficulty="easy",
            status="completed",
            outcome="success"
        )
        storage.save_task(task)

        # 验证状态
        state = storage.get_state()
        assert state.total_tasks == 1
        assert state.completed_tasks == 1

    def test_coach_multiple_tasks(self, tmp_path):
        """测试 Coach 处理多个任务"""
        temp_dir = str(tmp_path / "coach_multi")

        # 先创建目录
        import os
        os.makedirs(temp_dir, exist_ok=True)

        storage = CoachStorage(data_dir=temp_dir)

        # 创建多个任务
        goals = ["编程能力", "沟通能力", "分析能力"]
        for i, goal in enumerate(goals):
            task = CoachTask(
                task_id=f"task_{i}",
                business_goal=f"提高{goal}",
                task_description=f"关于{goal}的任务描述",
                difficulty="medium",
                status="completed",
                outcome="success" if i % 2 == 0 else "failure"
            )
            storage.save_task(task)

        # 验证统计
        state = storage.get_state()
        assert state.total_tasks == 3
        assert state.completed_tasks == 3
        assert state.successful_tasks == 2
        assert state.failed_tasks == 1

    def test_coach_task_persistence(self, tmp_path):
        """测试任务持久化"""
        temp_dir = str(tmp_path / "coach_persist")

        # 先创建目录
        import os
        os.makedirs(temp_dir, exist_ok=True)

        storage = CoachStorage(data_dir=temp_dir)

        # 保存任务
        task = CoachTask(
            task_id="persist_test",
            business_goal="测试持久化",
            task_description="测试任务描述",
            difficulty="hard",
            status="completed",
            outcome="success",
            coach_feedback="Excellent!",
            learned_skill_id="skill_001"
        )
        storage.save_task(task)

        # 重新加载
        loaded = storage.list_tasks()
        assert len(loaded) == 1
        assert loaded[0].task_id == "persist_test"
        assert loaded[0].coach_feedback == "Excellent!"


class TestCoachTaskModel:
    """CoachTask 模型测试"""

    def test_task_creation(self):
        """测试任务创建"""
        task = CoachTask(
            business_goal="提高编程能力",
            task_description="编写测试代码",
            difficulty="easy"
        )

        assert task.task_id is not None
        assert task.status == "pending"
        assert task.difficulty == "easy"
        assert task.outcome is None  # 默认是 None，不是 "unknown"

    def test_task_with_result(self):
        """测试带结果的任务"""
        task = CoachTask(
            business_goal="测试目标",
            task_description="测试描述",
            difficulty="medium"
        )

        # 更新任务状态
        task.status = "completed"
        task.outcome = "success"
        task.session_id = "session_123"
        task.coach_feedback = "做得好"

        assert task.status == "completed"
        assert task.outcome == "success"
        assert task.session_id == "session_123"


class TestCoachStateModel:
    """Coach 状态模型测试"""

    def test_initial_state(self):
        """测试初始状态"""
        from timem_evolve.models import CoachState

        state = CoachState()
        assert state.total_tasks == 0
        assert state.completed_tasks == 0
        assert state.successful_tasks == 0
        assert state.failed_tasks == 0
        assert state.skills_gained == 0
        assert state.rules_gained == 0

    def test_state_update(self):
        """测试状态更新"""
        from timem_evolve.models import CoachState

        state = CoachState()
        state.total_tasks = 5
        state.completed_tasks = 4
        state.successful_tasks = 3
        state.failed_tasks = 1
        state.skills_gained = 2
        state.rules_gained = 1

        assert state.total_tasks == 5
        assert state.completion_rate == 0.8  # 4/5
        assert state.success_rate == 0.75  # 3/4
