"""技能数据模型 v2 - 支持 E.S.P 和 M.S.F.S"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
import uuid


class Workflow(BaseModel):
    """工作流程"""
    steps: List[str] = Field(default_factory=list, description="执行步骤")
    sop: str = Field(default="", description="标准操作流程描述")


class SkillRouting(BaseModel):
    """技能路由配置

    用于决策引擎选择何时使用该技能
    """
    trigger_keywords: List[str] = Field(
        default_factory=list,
        description="触发关键词列表"
    )
    priority: int = Field(default=5, ge=1, le=10, description="优先级（1-10）")
    conditions: List[str] = Field(
        default_factory=list,
        description="触发条件（表达式，如 'language == \"python\"'）"
    )


class Skill(BaseModel):
    """技能数据模型 v2 - 支持 E.S.P 和 M.S.F.S

    特性:
    - 兼容 JSON 存储（向后兼容 v0.1.0）
    - 支持 Markdown 序列化（E.S.P）
    - 扩展元数据支持（路由、依赖、分类等）
    """
    # ==================== 核心字段 ====================
    skill_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(..., description="技能名称")
    description: str = Field(default="", description="技能描述")
    workflow: Workflow = Field(default_factory=Workflow, description="工作流程")

    # ==================== 来源与置信度 ====================
    source_sessions: List[str] = Field(
        default_factory=list,
        description="来源会话ID列表"
    )
    confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="置信度（0-1）"
    )

    # ==================== 时间戳 ====================
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    # ==================== 扩展元数据 ====================
    # 包含 E.S.P 所需的所有扩展字段
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="扩展元数据（category, version, routing, tags, dependencies 等）"
    )

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

    # ==================== E.S.P 便捷属性 ====================

    @property
    def category(self) -> str:
        """获取分类

        Returns:
            分类名称，默认为 "uncategorized"
        """
        return self.metadata.get("category", "uncategorized")

    @category.setter
    def category(self, value: str) -> None:
        """设置分类"""
        self.metadata["category"] = value

    @property
    def version(self) -> str:
        """获取版本号

        Returns:
            语义化版本号，默认为 "1.0.0"
        """
        return self.metadata.get("version", "1.0.0")

    @version.setter
    def version(self, value: str) -> None:
        """设置版本号"""
        self.metadata["version"] = value

    @property
    def tags(self) -> List[str]:
        """获取标签列表

        Returns:
            标签列表
        """
        return self.metadata.get("tags", [])

    @tags.setter
    def tags(self, value: List[str]) -> None:
        """设置标签"""
        self.metadata["tags"] = value

    @property
    def dependencies(self) -> List[str]:
        """获取依赖的其他技能 ID

        Returns:
            依赖技能 ID 列表
        """
        return self.metadata.get("dependencies", [])

    @dependencies.setter
    def dependencies(self, value: List[str]) -> None:
        """设置依赖"""
        self.metadata["dependencies"] = value

    @property
    def routing(self) -> SkillRouting:
        """获取路由配置

        Returns:
            SkillRouting 对象
        """
        routing_data = self.metadata.get("routing", {})
        return SkillRouting(**routing_data)

    @routing.setter
    def routing(self, value: SkillRouting | Dict[str, Any]) -> None:
        """设置路由配置"""
        if isinstance(value, SkillRouting):
            self.metadata["routing"] = value.model_dump()
        else:
            self.metadata["routing"] = value

    # ==================== E.S.P 数据提取方法 ====================

    def to_esp_dict(self) -> Dict[str, Any]:
        """转换为 E.S.P (Experience Serialization Protocol) 字典格式

        用于 RegistryDAO 生成 SKILL.md 时提取数据。

        Returns:
            包含所有 E.S.P 所需字段的字典

        结构:
            {
                "skill_id": "...",
                "name": "...",
                "description": "...",
                "category": "...",
                "version": "...",
                "author": "...",
                "tags": [...],
                "dependencies": [...],
                "routing": {...},
                "decision_table": [...],
                "applicable_scenarios": "...",
                "not_applicable_scenarios": "...",
                "best_practices_do": "...",
                "best_practices_dont": "...",
                "rules_must_do": [...],
                "rules_dont": [...],
                "prompt_template": "...",
            }
        """
        return {
            # 核心字段
            "skill_id": self.skill_id,
            "name": self.name,
            "description": self.description,
            "workflow_steps": self.workflow.steps,
            "workflow_sop": self.workflow.sop,

            # E.S.P 元数据
            "category": self.category,
            "version": self.version,
            "author": self.metadata.get("author", "TiMEM-Learner"),
            "confidence": self.confidence,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),

            # 分类与标签
            "tags": self.tags,
            "dependencies": self.dependencies,

            # 路由配置
            "routing": self.routing.model_dump(),

            # 决策表（快速决策）
            "decision_table": self.metadata.get("decision_table", []),

            # 场景描述
            "applicable_scenarios": self.metadata.get("applicable_scenarios", "待补充"),
            "not_applicable_scenarios": self.metadata.get("not_applicable_scenarios", "待补充"),

            # 最佳实践
            "best_practices_do": self.metadata.get("best_practices_do", "待补充"),
            "best_practices_dont": self.metadata.get("best_practices_dont", "待补充"),

            # 规则（高内聚）
            "rules_must_do": self.metadata.get("rules_must_do", []),
            "rules_dont": self.metadata.get("rules_dont", []),

            # 实现相关
            "prompt_template": self.metadata.get("prompt_template", ""),
            "code_implementation": self.metadata.get("code_implementation", ""),
            "test_code": self.metadata.get("test_code", ""),

            # 来源
            "source_sessions": self.source_sessions,
        }

    @classmethod
    def from_esp_dict(
        cls,
        esp_dict: Dict[str, Any],
        workflow: Optional[Workflow] = None
    ) -> "Skill":
        """从 E.S.P 字典创建 Skill 对象

        Args:
            esp_dict: E.S.P 格式的字典
            workflow: 可选的工作流程对象

        Returns:
            Skill 对象
        """
        # 构建元数据
        metadata = {
            "category": esp_dict.get("category", "uncategorized"),
            "version": esp_dict.get("version", "1.0.0"),
            "author": esp_dict.get("author", "TiMEM-Learner"),
            "tags": esp_dict.get("tags", []),
            "dependencies": esp_dict.get("dependencies", []),
            "routing": esp_dict.get("routing", {}),
            "decision_table": esp_dict.get("decision_table", []),
            "applicable_scenarios": esp_dict.get("applicable_scenarios", "待补充"),
            "not_applicable_scenarios": esp_dict.get("not_applicable_scenarios", "待补充"),
            "best_practices_do": esp_dict.get("best_practices_do", "待补充"),
            "best_practices_dont": esp_dict.get("best_practices_dont", "待补充"),
            "rules_must_do": esp_dict.get("rules_must_do", []),
            "rules_dont": esp_dict.get("rules_dont", []),
            "prompt_template": esp_dict.get("prompt_template", ""),
        }

        # 如果有代码实现，也加入元数据
        if "code_implementation" in esp_dict:
            metadata["code_implementation"] = esp_dict["code_implementation"]
        if "test_code" in esp_dict:
            metadata["test_code"] = esp_dict["test_code"]

        # 构建工作流程
        if workflow is None:
            workflow = Workflow(
                steps=esp_dict.get("workflow_steps", []),
                sop=esp_dict.get("workflow_sop", "")
            )

        return cls(
            skill_id=esp_dict.get("skill_id", str(uuid.uuid4())),
            name=esp_dict.get("name", ""),
            description=esp_dict.get("description", ""),
            workflow=workflow,
            source_sessions=esp_dict.get("source_sessions", []),
            confidence=esp_dict.get("confidence", 0.5),
            created_at=datetime.fromisoformat(esp_dict["created_at"]) if esp_dict.get("created_at") else datetime.now(),
            updated_at=datetime.fromisoformat(esp_dict["updated_at"]) if esp_dict.get("updated_at") else datetime.now(),
            metadata=metadata
        )

    # ==================== 版本管理 ====================

    def increment_version(
        self,
        increment_type: str = "patch"
    ) -> tuple[str, str]:
        """版本号自增

        Args:
            increment_type: 自增类型 ("major", "minor", "patch")

        Returns:
            (旧版本号, 新版本号) 元组
        """
        old_version = self.version

        try:
            major, minor, patch = map(int, old_version.split("."))
        except (ValueError, AttributeError):
            major, minor, patch = 1, 0, 0

        if increment_type == "major":
            major += 1
            minor = 0
            patch = 0
        elif increment_type == "minor":
            minor += 1
            patch = 0
        else:  # patch
            patch += 1

        new_version = f"{major}.{minor}.{patch}"
        self.version = new_version

        return old_version, new_version

    # ==================== 实用方法 ====================

    def add_tag(self, tag: str) -> None:
        """添加标签（去重）"""
        tags = self.tags
        if tag not in tags:
            tags.append(tag)
        self.tags = tags

    def add_dependency(self, skill_id: str) -> None:
        """添加依赖（去重）"""
        deps = self.dependencies
        if skill_id not in deps:
            deps.append(skill_id)
        self.dependencies = deps

    def add_source_session(self, session_id: str) -> None:
        """添加来源会话（去重）"""
        if session_id not in self.source_sessions:
            self.source_sessions.append(session_id)

    def touch(self) -> None:
        """更新 updated_at 时间戳"""
        self.updated_at = datetime.now()
