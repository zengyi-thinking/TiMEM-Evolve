"""学习器 - 从会话和反馈中提炼技能和规则 (v2.0)

支持:
- UnifiedDAO 适配器（自动路由到 RegistryDAO 或 MemoryDAO）
- E.S.P 格式的技能提炼（包含 SkillRouting、决策表、最佳实践）
- 从反馈和完整会话中学习
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional
from langchain_core.messages import HumanMessage

from ..dao import UnifiedDAO
from ..models import (
    Feedback,
    Rule,
    Session,
    Skill,
    SkillRouting,
    Workflow,
)
from .utils import create_chat_model


class LearnerService:
    """经验学习器 v2.0

    职责:
    - 从用户反馈中学习（好评→技能，差评→规则）
    - 从完整会话中学习（成功→技能，失败→规则）
    - 生成符合 E.S.P 规范的技能结构
    """

    def __init__(self, dao: UnifiedDAO, model_name: str = "gpt-4.1-mini"):
        """初始化学习器

        Args:
            dao: UnifiedDAO 实例（自动路由到正确的后端）
            model_name: LLM 模型名称
        """
        self.dao = dao
        self.llm = create_chat_model(model_name=model_name, temperature=0.7)

    async def learn_from_feedback(self, feedback: Feedback) -> Optional[str]:
        """从单轮反馈中学习

        Args:
            feedback: 用户反馈对象

        Returns:
            学到的 skill_id 或 rule_id
        """
        # 获取会话
        session = await self.dao.get_session(feedback.session_id)
        if not session:
            return None

        # 获取对应的消息对（用户消息 + AI回复）
        if feedback.message_index < 0 or feedback.message_index >= len(session.messages):
            return None

        # 构建上下文
        context_messages = session.messages[:feedback.message_index + 1]
        current_turn = self._extract_dialog_turn(context_messages, feedback.message_index)

        if feedback.rating == "positive":
            # 好评 -> 提炼技能
            skill = await self._extract_skill_from_turn(
                task=session.task,
                dialog_turn=current_turn,
                feedback_comment=feedback.comment,
                session=session
            )
            if skill:
                skill.source_sessions = [session.session_id]
                skill.metadata["feedback_id"] = feedback.feedback_id

                # 使用 UnifiedDAO 保存（自动路由到 RegistryDAO 或 MemoryDAO）
                await self.dao.save_skill(skill, change_summary="从反馈中学习")

                # 更新反馈状态
                feedback.learned = True
                feedback.learned_skill_id = skill.skill_id
                self.dao.save_feedback(feedback)

                return skill.skill_id
        else:
            # 差评 -> 提炼规则
            rule = await self._extract_rule_from_turn(
                task=session.task,
                dialog_turn=current_turn,
                feedback_comment=feedback.comment
            )
            if rule:
                rule.source_sessions = [session.session_id]
                rule.metadata["feedback_id"] = feedback.feedback_id
                self.dao.save_rule(rule)

                # 更新反馈状态
                feedback.learned = True
                feedback.learned_rule_id = rule.rule_id
                self.dao.save_feedback(feedback)

                return rule.rule_id

        return None

    def _extract_dialog_turn(self, messages: List, current_index: int) -> Dict[str, Any]:
        """提取对话轮次

        Args:
            messages: 消息列表
            current_index: 当前消息索引

        Returns:
            包含 user_message, ai_response, context 的字典
        """
        # 找到当前 AI 回复对应的用户消息
        user_msg = None
        ai_msg = messages[current_index]

        # 向前查找最近的用户消息
        for i in range(current_index - 1, -1, -1):
            msg = messages[i]
            role = msg.role if hasattr(msg, 'role') else msg.get('role')
            if role == "user":
                user_msg = msg
                break

        return {
            "user_message": user_msg.content if user_msg else "",
            "ai_response": ai_msg.content if hasattr(ai_msg, 'content') else ai_msg.get('content', ''),
            "context": self._format_messages(messages[:current_index])
        }

    def _format_messages(self, messages: List) -> str:
        """格式化消息为字符串

        Args:
            messages: 消息列表

        Returns:
            格式化后的字符串
        """
        formatted = []
        for msg in messages:
            role = msg.role if hasattr(msg, 'role') else msg.get('role', 'unknown')
            content = msg.content if hasattr(msg, 'content') else msg.get('content', '')
            formatted.append(f"{role}: {content}")
        return "\n".join(formatted)

    async def _extract_skill_from_turn(
        self,
        task: str,
        dialog_turn: Dict[str, Any],
        feedback_comment: Optional[str],
        session: Session
    ) -> Optional[Skill]:
        """从好评的对话轮次中提炼技能（E.S.P 格式）

        Returns:
            符合 E.S.P 规范的 Skill 对象
        """

        prompt = f"""
基于以下用户好评的对话，提炼一个可复用的技能。

任务背景: {task}

对话上下文:
{dialog_turn['context']}

当前对话轮次:
用户: {dialog_turn['user_message']}
AI: {dialog_turn['ai_response']}

用户反馈: {feedback_comment or '好评'}

请分析这个AI回复为什么获得好评，并提炼成一个可复用的技能。

以 JSON 格式返回：
{{
    "name": "技能名称（简短，例如：清晰的代码解释）",
    "description": "技能描述（1-2句话，说明这个技能是什么）",
    "category": "技能分类（programming, communication, analysis, search, writing, other）",
    "steps": ["步骤1", "步骤2", "步骤3"],
    "sop": "详细的标准操作流程描述（如何应用这个技能）",
    "trigger_keywords": ["关键词1", "关键词2"],  // 触发技能的关键词
    "applicable_scenarios": "适用场景描述",
    "not_applicable_scenarios": "不适用场景描述",
    "best_practices_do": "最佳实践 - 应该做什么",
    "best_practices_dont": "最佳实践 - 不应该做什么",
    "confidence": 0.8
}}

只返回 JSON，不要其他内容。
"""

        try:
            response = await self.llm.ainvoke([HumanMessage(content=prompt)])
            content = response.content.strip()

            # 提取 JSON
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            data = json.loads(content)

            # 构建 SkillRouting
            routing = SkillRouting(
                trigger_keywords=data.get("trigger_keywords", []),
                priority=5,
                conditions=[]
            )

            # 构建完整的 E.S.P 元数据
            metadata = {
                # 基础字段
                "category": data.get("category", self._infer_category(data["name"], data["description"])),
                "version": "1.0.0",
                "author": "TiMEM-Learner",

                # 场景描述
                "applicable_scenarios": data.get("applicable_scenarios", "待补充"),
                "not_applicable_scenarios": data.get("not_applicable_scenarios", "待补充"),

                # 最佳实践
                "best_practices_do": data.get("best_practices_do", "待补充"),
                "best_practices_dont": data.get("best_practices_dont", "待补充"),

                # 路由配置
                "routing": routing.model_dump(),

                # 规则（高内聚）
                "rules_must_do": [],
                "rules_dont": [],

                # 决策表（从场景生成）
                "decision_table": self._generate_decision_table_from_scenarios(
                    data.get("applicable_scenarios", ""),
                    data.get("not_applicable_scenarios", "")
                ),

                # 来源
                "feedback_id": None,  # 将在调用处设置
                "learned_from": "feedback",
            }

            return Skill(
                name=data["name"],
                description=data["description"],
                workflow=Workflow(
                    steps=data["steps"],
                    sop=data["sop"]
                ),
                confidence=data.get("confidence", 0.7),
                metadata=metadata
            )

        except Exception as e:
            print(f"提炼技能失败: {e}")
            return None

    async def _extract_rule_from_turn(
        self,
        task: str,
        dialog_turn: Dict[str, Any],
        feedback_comment: Optional[str]
    ) -> Optional[Rule]:
        """从差评的对话轮次中提炼规则"""

        prompt = f"""
基于以下用户差评的对话，提炼一个约束规则。

任务背景: {task}

对话上下文:
{dialog_turn['context']}

当前对话轮次:
用户: {dialog_turn['user_message']}
AI: {dialog_turn['ai_response']}

用户反馈: {feedback_comment or '差评'}

请分析这个AI回复为什么获得差评，并提炼成一个约束规则，避免未来犯同样的错误。

以 JSON 格式返回：
{{
    "name": "规则名称（简短，例如：避免过于技术化的解释）",
    "description": "规则描述（1-2句话，说明这个规则是什么）",
    "constraint": "约束条件（应该避免什么行为）",
    "reason": "原因说明（为什么需要这个规则）",
    "confidence": 0.8
}}

只返回 JSON，不要其他内容。
"""

        try:
            response = await self.llm.ainvoke([HumanMessage(content=prompt)])
            content = response.content.strip()

            # 提取 JSON
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            data = json.loads(content)

            return Rule(
                name=data["name"],
                description=data["description"],
                constraint=data["constraint"],
                reason=data["reason"],
                confidence=data.get("confidence", 0.7)
            )

        except Exception as e:
            print(f"提炼规则失败: {e}")
            return None

    async def extract_skill_from_session(self, session: Session) -> Optional[Skill]:
        """从成功的完整会话中提炼技能（E.S.P 格式）"""

        prompt = f"""
基于以下成功的任务会话，提炼一个可复用的技能。

任务: {session.task}

会话消息:
{self._format_messages(session.messages)}

请分析这个任务是如何成功完成的，并提炼成一个可复用的技能。

以 JSON 格式返回：
{{
    "name": "技能名称",
    "description": "技能描述",
    "category": "技能分类（programming, communication, analysis, search, writing, other）",
    "steps": ["步骤1", "步骤2", "步骤3"],
    "sop": "详细的标准操作流程描述",
    "trigger_keywords": ["关键词1", "关键词2"],
    "applicable_scenarios": "适用场景",
    "not_applicable_scenarios": "不适用场景",
    "best_practices_do": "应该做什么",
    "best_practices_dont": "不应该做什么",
    "confidence": 0.8
}}

只返回 JSON，不要其他内容。
"""

        try:
            response = await self.llm.ainvoke([HumanMessage(content=prompt)])
            content = response.content.strip()

            # 提取 JSON
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            data = json.loads(content)

            # 构建 SkillRouting
            routing = SkillRouting(
                trigger_keywords=data.get("trigger_keywords", []),
                priority=5,
                conditions=[]
            )

            # 构建 E.S.P 元数据
            metadata = {
                "category": data.get("category", self._infer_category(data["name"], data["description"])),
                "version": "1.0.0",
                "author": "TiMEM-Learner",
                "applicable_scenarios": data.get("applicable_scenarios", "待补充"),
                "not_applicable_scenarios": data.get("not_applicable_scenarios", "待补充"),
                "best_practices_do": data.get("best_practices_do", "待补充"),
                "best_practices_dont": data.get("best_practices_dont", "待补充"),
                "routing": routing.model_dump(),
                "rules_must_do": [],
                "rules_dont": [],
                "decision_table": self._generate_decision_table_from_scenarios(
                    data.get("applicable_scenarios", ""),
                    data.get("not_applicable_scenarios", "")
                ),
                "learned_from": "session",
            }

            skill = Skill(
                name=data["name"],
                description=data["description"],
                workflow=Workflow(
                    steps=data["steps"],
                    sop=data["sop"]
                ),
                confidence=data.get("confidence", 0.7),
                source_sessions=[session.session_id],
                metadata=metadata
            )

            # 使用 UnifiedDAO 保存
            await self.dao.save_skill(skill, change_summary="从会话中学习")
            return skill

        except Exception as e:
            print(f"提炼技能失败: {e}")
            return None

    async def extract_rule_from_session(self, session: Session) -> Optional[Rule]:
        """从失败的完整会话中提炼规则"""

        prompt = f"""
基于以下失败的任务会话，提炼一个约束规则。

任务: {session.task}

会话消息:
{self._format_messages(session.messages)}

请分析这个任务为什么失败，并提炼成一个约束规则。

以 JSON 格式返回：
{{
    "name": "规则名称",
    "description": "规则描述",
    "constraint": "约束条件",
    "reason": "原因说明",
    "confidence": 0.8
}}

只返回 JSON，不要其他内容。
"""

        try:
            response = await self.llm.ainvoke([HumanMessage(content=prompt)])
            content = response.content.strip()

            # 提取 JSON
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            data = json.loads(content)

            rule = Rule(
                name=data["name"],
                description=data["description"],
                constraint=data["constraint"],
                reason=data["reason"],
                confidence=data.get("confidence", 0.7),
                source_sessions=[session.session_id]
            )

            self.dao.save_rule(rule)
            return rule

        except Exception as e:
            print(f"提炼规则失败: {e}")
            return None

    # ==================== 辅助方法 ====================

    def _infer_category(self, name: str, description: str) -> str:
        """从名称和描述推断分类

        Args:
            name: 技能名称
            description: 技能描述

        Returns:
            分类名称
        """
        text = f"{name} {description}".lower()

        category_keywords = {
            "programming": ["代码", "编程", "debug", "调试", "开发", "重构", "测试", "函数"],
            "communication": ["沟通", "对话", "回复", "解释", "说明", "咨询", "交流"],
            "analysis": ["分析", "评估", "诊断", "检查", "审核", "理解"],
            "search": ["搜索", "检索", "查询", "查找", "寻找"],
            "writing": ["写作", "文档", "生成", "撰写", "创作"],
        }

        for category, keywords in category_keywords.items():
            if any(keyword in text for keyword in keywords):
                return category

        return "other"

    def _generate_decision_table_from_scenarios(
        self,
        applicable: str,
        not_applicable: str
    ) -> List[Dict[str, Any]]:
        """从场景描述生成快速决策表

        Args:
            applicable: 适用场景
            not_applicable: 不适用场景

        Returns:
            决策表列表
        """
        table = []

        if applicable:
            table.append({
                "condition": applicable[:50] + "..." if len(applicable) > 50 else applicable,
                "action": "使用本技能",
                "priority": "高",
                "note": "适用场景"
            })

        if not_applicable:
            table.append({
                "condition": not_applicable[:50] + "..." if len(not_applicable) > 50 else not_applicable,
                "action": "不使用本技能 / 委托给其他技能",
                "priority": "中",
                "note": "不适用场景"
            })

        # 默认行
        if not table:
            table.append({
                "condition": "相关请求",
                "action": "使用本技能",
                "priority": "中",
                "note": "待人工优化"
            })

        return table
