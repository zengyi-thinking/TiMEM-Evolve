"""统一数据访问对象 (Unified DAO) - 适配器模式

实现 v0.1.0 (MemoryDAO) 和 v0.2.0 (RegistryDAO) 的统一接口，
支持向后兼容和渐进式迁移。

环境变量:
    USE_SKILL_REGISTRY: 是否使用 M.S.F.S 技能注册表 (默认: true)
        - true: 技能使用 RegistryDAO，会话/反馈使用 MemoryDAO
        - false: 所有数据使用 MemoryDAO（向后兼容 v0.1.0）
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from ..models import Feedback, Rule, Session, Skill


class UnifiedDAO:
    """统一数据访问对象

    职责:
    - 提供统一的异步接口给 Service 层
    - 根据配置路由到不同的 DAO 实现
    - 支持向后兼容和渐进式迁移

    路由策略:
        - Sessions → MemoryDAO (SQLite)
        - Feedbacks → MemoryDAO (JSON)
        - Skills → RegistryDAO (M.S.F.S) 或 MemoryDAO (JSON)
        - Rules → MemoryDAO (JSON)
    """

    def __init__(
        self,
        data_dir: str = "./data",
        use_registry: Optional[bool] = None
    ):
        """初始化统一 DAO

        Args:
            data_dir: 数据目录路径
            use_registry: 是否使用技能注册表
                - None: 从环境变量 USE_SKILL_REGISTRY 读取
                - True: 使用 RegistryDAO (M.S.F.S)
                - False: 使用 MemoryDAO (JSON)
        """
        self.data_dir = data_dir

        # 确定 use_registry 配置
        if use_registry is None:
            use_registry = os.getenv("USE_SKILL_REGISTRY", "true").lower() == "true"

        self.use_registry = use_registry

        # 延迟导入，避免循环依赖
        from .memory_dao import MemoryDAO
        self.memory_dao = MemoryDAO(data_dir)

        # 仅在需要时初始化 RegistryDAO
        self._registry_dao = None

    @property
    def registry_dao(self):
        """延迟初始化 RegistryDAO"""
        if self._registry_dao is None:
            from .registry_dao import RegistryDAO
            knowledge_base_dir = f"{self.data_dir}/knowledge_base"
            self._registry_dao = RegistryDAO(knowledge_base_dir)
        return self._registry_dao

    # ==================== Sessions ====================
    # 始终使用 MemoryDAO (SQLite)

    async def init_db(self) -> None:
        """初始化数据库"""
        return await self.memory_dao.init_db()

    async def save_session(self, session: Session) -> None:
        """保存会话"""
        return await self.memory_dao.save_session(session)

    async def get_session(self, session_id: str) -> Optional[Session]:
        """获取会话"""
        return await self.memory_dao.get_session(session_id)

    async def list_sessions(
        self,
        outcome: Optional[str] = None,
        limit: int = 100
    ) -> List[Session]:
        """列出会话"""
        return await self.memory_dao.list_sessions(outcome=outcome, limit=limit)

    # ==================== Skills ====================
    # 根据 use_registry 配置路由

    async def save_skill(
        self,
        skill: Skill,
        change_summary: Optional[str] = None
    ) -> str | None:
        """保存技能

        Args:
            skill: 技能对象
            change_summary: 变更摘要（仅 RegistryDAO 使用）

        Returns:
            RegistryDAO: 技能容器路径
            MemoryDAO: None
        """
        if self.use_registry:
            return await self.registry_dao.save_skill_container(skill, change_summary)
        else:
            # MemoryDAO.save_skill 是同步的，需要包装
            self.memory_dao.save_skill(skill)
            return None

    async def get_skill(self, skill_id: str) -> Optional[Skill]:
        """获取技能"""
        if self.use_registry:
            return await self.registry_dao.get_skill_container(skill_id)
        else:
            return self.memory_dao.get_skill(skill_id)

    async def list_skills(
        self,
        category: Optional[str] = None,
        limit: int = 100,
        load_full: bool = False
    ) -> List[Skill]:
        """列出技能

        Args:
            category: 可选分类过滤（仅 RegistryDAO 支持）
            limit: 最大返回数量
            load_full: 是否加载完整技能（仅 RegistryDAO 支持，MemoryDAO 忽略）

        Note: load_full 参数仅 RegistryDAO 支持，MemoryDAO 会忽略
        """
        if self.use_registry:
            return await self.registry_dao.list_skill_containers(
                category=category,
                limit=limit,
                load_full=load_full
            )
        else:
            return self.memory_dao.list_skills(limit=limit)

    async def search_skills(
        self,
        query: str,
        category: Optional[str] = None,
        top_k: int = 5
    ) -> List[Skill]:
        """搜索技能

        Note: category 参数仅 RegistryDAO 支持，MemoryDAO 会忽略
        """
        if self.use_registry:
            return await self.registry_dao.search_skill_containers(
                query=query,
                category=category,
                top_k=top_k
            )
        else:
            return self.memory_dao.search_skills(query=query, top_k=top_k)

    async def update_skill(
        self,
        skill_id: str,
        updates: Dict[str, Any],
        change_summary: str
    ) -> Optional[Skill]:
        """更新技能

        Note: change_summary 参数仅 RegistryDAO 支持

        Returns:
            更新后的 Skill 对象，如果技能不存在则返回 None
        """
        if self.use_registry:
            return await self.registry_dao.update_skill_container(
                skill_id=skill_id,
                updates=updates,
                change_summary=change_summary
            )
        else:
            # MemoryDAO 不支持 update，需要先获取再保存
            skill = self.memory_dao.get_skill(skill_id)
            if not skill:
                return None

            # 应用更新
            for key, value in updates.items():
                if hasattr(skill, key):
                    setattr(skill, key, value)
                else:
                    skill.metadata[key] = value

            self.memory_dao.save_skill(skill)
            return skill

    async def delete_skill(self, skill_id: str) -> bool:
        """删除技能

        Returns:
            是否成功删除
        """
        if self.use_registry:
            return await self.registry_dao.delete_skill_container(skill_id)
        else:
            # MemoryDAO 不支持删除，返回 False
            return False

    # ==================== Rules ====================
    # 始终使用 MemoryDAO (JSON)

    def save_rule(self, rule: Rule) -> None:
        """保存规则"""
        return self.memory_dao.save_rule(rule)

    def get_rule(self, rule_id: str) -> Optional[Rule]:
        """获取规则"""
        return self.memory_dao.get_rule(rule_id)

    def list_rules(self, limit: int = 100) -> List[Rule]:
        """列出规则"""
        return self.memory_dao.list_rules(limit=limit)

    def search_rules(self, query: str, top_k: int = 5) -> List[Rule]:
        """搜索规则"""
        return self.memory_dao.search_rules(query=query, top_k=top_k)

    # ==================== Feedbacks ====================
    # 始终使用 MemoryDAO (JSON)

    def save_feedback(self, feedback: Feedback) -> None:
        """保存反馈"""
        return self.memory_dao.save_feedback(feedback)

    def get_feedback(self, feedback_id: str) -> Optional[Feedback]:
        """获取反馈"""
        return self.memory_dao.get_feedback(feedback_id)

    def list_feedbacks(
        self,
        session_id: Optional[str] = None,
        learned: Optional[bool] = None,
        limit: int = 100
    ) -> List[Feedback]:
        """列出反馈"""
        return self.memory_dao.list_feedbacks(
            session_id=session_id,
            learned=learned,
            limit=limit
        )

    # ==================== 配置管理 ====================

    def get_backend_info(self) -> Dict[str, Any]:
        """获取当前后端配置信息

        Returns:
            包含后端配置的字典
        """
        return {
            "use_skill_registry": self.use_registry,
            "skills_backend": "RegistryDAO (M.S.F.S)" if self.use_registry else "MemoryDAO (JSON)",
            "sessions_backend": "MemoryDAO (SQLite)",
            "rules_backend": "MemoryDAO (JSON)",
            "feedbacks_backend": "MemoryDAO (JSON)",
            "data_dir": self.data_dir,
            "knowledge_base_dir": f"{self.data_dir}/knowledge_base" if self.use_registry else None,
        }

    def is_using_registry(self) -> bool:
        """是否使用技能注册表"""
        return self.use_registry

    # ==================== 技能扩展操作 ====================
    # 仅 RegistryDAO 支持的功能

    async def get_evolution_log(self, skill_id: str) -> List[Dict[str, str]]:
        """获取技能的变更历史

        Args:
            skill_id: 技能 ID

        Returns:
            变更历史记录列表，每项包含 timestamp, version, summary, source
            如果使用 MemoryDAO 或技能不存在，返回空列表
        """
        if self.use_registry:
            return await self.registry_dao.get_evolution_log(skill_id)
        else:
            return []

    async def export_skill_markdown(self, skill_id: str) -> Optional[str]:
        """导出技能为 E.S.P Markdown 格式

        Args:
            skill_id: 技能 ID

        Returns:
            Markdown 字符串，如果使用 MemoryDAO 或技能不存在则返回 None
        """
        if self.use_registry:
            return await self.registry_dao.export_skill_markdown(skill_id)
        else:
            return None

    async def import_skill_from_markdown(
        self,
        markdown_content: str,
        skill_id: Optional[str] = None
    ) -> Optional[Skill]:
        """从 Markdown 导入技能

        Args:
            markdown_content: E.S.P 格式的 Markdown 内容
            skill_id: 可选的技能 ID（如果提供，将覆盖 Markdown 中的 ID）

        Returns:
            导入的 Skill 对象，如果使用 MemoryDAO 或解析失败则返回 None
        """
        if self.use_registry:
            return await self.registry_dao.import_skill_from_markdown(
                markdown_content=markdown_content,
                skill_id=skill_id
            )
        else:
            return None

    async def rebuild_index(self) -> Dict[str, Any]:
        """重建技能索引

        扫描 skills/ 目录，重新构建 _index.json

        Returns:
            重建结果摘要，包含 total_skills, successful, failed, failed_skills
            如果使用 MemoryDAO，返回空结果
        """
        if self.use_registry:
            return await self.registry_dao.rebuild_index()
        else:
            return {
                "total_skills": 0,
                "successful": 0,
                "failed": 0,
                "failed_skills": [],
                "message": "MemoryDAO 不支持索引重建"
            }

    async def increment_skill_version(
        self,
        skill_id: str,
        increment_type: str = "patch",
        change_summary: Optional[str] = None
    ) -> Optional[Skill]:
        """创建技能的新版本

        Args:
            skill_id: 技能 ID
            increment_type: 版本自增类型 ("major", "minor", "patch")
            change_summary: 变更摘要

        Returns:
            更新后的 Skill 对象，如果技能不存在或使用 MemoryDAO 则返回 None
        """
        if self.use_registry:
            return await self.registry_dao.increment_skill_version(
                skill_id=skill_id,
                increment_type=increment_type,
                change_summary=change_summary
            )
        else:
            return None
