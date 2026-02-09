"""M.S.F.S 知识注册表 DAO - 文件系统存储

实现了模块化技能文件系统（M.S.F.S），支持 E.S.P 格式的技能容器管理。

目录结构:
    data/knowledge_base/
    ├── skills/{category}/{skill_id}/
    │   ├── SKILL.md          # E.S.P 规范的主文档
    │   ├── RULES.md          # 技能专属规则（高内聚）
    │   ├── impl/             # 实现层
    │   │   ├── prompt.txt
    │   │   ├── code.py
    │   │   └── test.py
    │   ├── evolution.log     # 变更历史
    │   └── metadata.json
    ├── _index.json           # 技能索引
    └── _registry.lock
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiofiles
import frontmatter
import yaml

from ..models import Skill, Workflow


class RegistryDAO:
    """M.S.F.S 知识注册表管理器

    职责:
    - 管理技能容器（文件系统）
    - 读写 SKILL.md (E.S.P 格式)
    - 维护索引（_index.json）
    - 追踪变更历史（evolution.log）

    Attributes:
        kb_dir: 知识库根目录
        skills_dir: 技能容器目录
        rules_dir: 规则容器目录
        index_path: 索引文件路径
    """

    def __init__(self, knowledge_base_dir: str = "./data/knowledge_base"):
        """初始化注册表

        Args:
            knowledge_base_dir: 知识库根目录路径
        """
        self.kb_dir: Path = Path(knowledge_base_dir)
        self.skills_dir: Path = self.kb_dir / "skills"
        self.rules_dir: Path = self.kb_dir / "rules"
        self.index_path: Path = self.kb_dir / "_index.json"
        self.lock_path: Path = self.kb_dir / "_registry.lock"

        # 初始化目录结构
        self._init_directories()

    # ==================== 目录初始化 ====================

    def _init_directories(self) -> None:
        """初始化 M.S.F.S 目录结构

        创建必要的目录:
        - knowledge_base/
        - skills/
        - rules/
        """
        self.kb_dir.mkdir(parents=True, exist_ok=True)
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self.rules_dir.mkdir(parents=True, exist_ok=True)

        # 如果索引不存在，创建空索引
        if not self.index_path.exists():
            self._create_empty_index()

    def _create_empty_index(self) -> None:
        """创建空的索引文件"""
        empty_index = {
            "skills": {},
            "rules": {},
            "last_updated": None,
            "version": "2.0.0",
        }
        self.index_path.write_text(
            json.dumps(empty_index, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

    # ==================== 索引管理 ====================

    async def _load_index(self) -> Dict[str, Any]:
        """加载索引文件

        Returns:
            索引字典，包含 skills 和 rules 映射
        """
        if not self.index_path.exists():
            self._create_empty_index()

        async with aiofiles.open(self.index_path, "r", encoding="utf-8") as f:
            content = await f.read()
            return json.loads(content) if content else {
                "skills": {},
                "rules": {},
                "last_updated": None,
                "version": "2.0.0",
            }

    async def _save_index(self, index: Dict[str, Any]) -> None:
        """保存索引文件

        Args:
            index: 索引字典
        """
        index["last_updated"] = datetime.now().isoformat()
        index["version"] = "2.0.0"

        async with aiofiles.open(self.index_path, "w", encoding="utf-8") as f:
            await f.write(json.dumps(index, indent=2, ensure_ascii=False))

    async def _update_index(self, skill: Skill) -> None:
        """更新索引中的技能条目

        Args:
            skill: 要更新索引的技能对象
        """
        index = await self._load_index()

        category = skill.metadata.get("category", "uncategorized")
        relative_path = f"skills/{category}/{skill.skill_id}"

        # 提取路由关键词
        routing = skill.metadata.get("routing", {})
        trigger_keywords = routing.get("trigger_keywords", [])

        index["skills"][skill.skill_id] = {
            "name": skill.name,
            "description": skill.description,
            "category": category,
            "path": relative_path,
            "version": skill.metadata.get("version", "1.0.0"),
            "tags": skill.metadata.get("tags", []),
            "trigger_keywords": trigger_keywords,
            "confidence": skill.confidence,
            "created_at": skill.created_at.isoformat(),
            "updated_at": skill.updated_at.isoformat(),
        }

        await self._save_index(index)

    async def _remove_from_index(self, skill_id: str) -> None:
        """从索引中移除技能

        Args:
            skill_id: 要移除的技能 ID
        """
        index = await self._load_index()

        if skill_id in index.get("skills", {}):
            del index["skills"][skill_id]
            await self._save_index(index)

    # ==================== SKILL.md 读写 ====================

    async def _write_skill_md(self, skill_dir: Path, skill: Skill) -> None:
        """写入 SKILL.md (E.S.P 格式)

        Args:
            skill_dir: 技能容器目录
            skill: 技能对象

        SKILL.md 格式:
            ---
            # Frontmatter (元数据)
            skill_id: "xxx"
            name: "技能名称"
            ...
            ---

            # 技能名称
            技能描述...

            ## ⚡ 快速决策表
            | 条件 | 行动 | 优先级 | 备注 |
            ...
        """
        # 确保目录存在
        skill_dir.mkdir(parents=True, exist_ok=True)

        skill_md_path = skill_dir / "SKILL.md"

        # 1. 构建 Frontmatter
        frontmatter_data = {
            "skill_id": skill.skill_id,
            "name": skill.name,
            "description": skill.description,
            "category": skill.metadata.get("category", "uncategorized"),
            "version": skill.metadata.get("version", "1.0.0"),
            "created_at": skill.created_at.isoformat(),
            "updated_at": skill.updated_at.isoformat(),
            "author": skill.metadata.get("author", "TiMEM-Learner"),
            "confidence": skill.confidence,
            "source_sessions": skill.source_sessions,
            "tags": skill.metadata.get("tags", []),
            "dependencies": skill.metadata.get("dependencies", []),
            "routing": skill.metadata.get("routing", {}),
        }

        # 2. 生成 Markdown 正文
        content = self._generate_skill_markdown_content(skill)

        # 3. 使用手动方式写入 frontmatter（兼容新版 frontmatter）
        full_content = self._format_frontmatter(frontmatter_data, content)

        async with aiofiles.open(skill_md_path, "w", encoding="utf-8") as f:
            await f.write(full_content)

    async def _parse_skill_md(self, skill_md_path: Path) -> Optional[Skill]:
        """解析 SKILL.md (E.S.P 格式)

        Args:
            skill_md_path: SKILL.md 文件路径

        Returns:
            解析后的 Skill 对象，如果解析失败则返回 None
        """
        try:
            async with aiofiles.open(skill_md_path, "r", encoding="utf-8") as f:
                content = await f.read()

            # 使用新版 frontmatter API
            result = frontmatter.Frontmatter.read(content)

            # 从 Frontmatter 提取元数据
            metadata = dict(result.get("attributes", {}))

            # 确保 category 在 metadata 中
            metadata["category"] = metadata.get("category", "uncategorized")
            metadata["version"] = metadata.get("version", "1.0.0")
            metadata["author"] = metadata.get("author", "TiMEM-Learner")
            metadata["tags"] = metadata.get("tags", [])
            metadata["dependencies"] = metadata.get("dependencies", [])
            metadata["routing"] = metadata.get("routing", {})

            # 从 Markdown 正文提取工作流程
            body = result.get("body", "")
            steps = self._extract_steps_from_markdown(body)
            sop = self._extract_sop_from_markdown(body)

            # 构造 Skill 对象
            return Skill(
                skill_id=metadata["skill_id"],
                name=metadata["name"],
                description=metadata.get("description", ""),
                workflow=Workflow(steps=steps, sop=sop),
                source_sessions=metadata.get("source_sessions", []),
                confidence=metadata.get("confidence", 0.5),
                created_at=datetime.fromisoformat(metadata["created_at"]),
                updated_at=datetime.fromisoformat(metadata["updated_at"]),
                metadata=metadata
            )

        except Exception as e:
            # 解析失败，记录错误并返回 None
            print(f"解析 SKILL.md 失败 ({skill_md_path}): {e}")
            return None

    def _format_frontmatter(self, attributes: Dict[str, Any], body: str) -> str:
        """格式化 frontmatter 为字符串（兼容新版 frontmatter）

        Args:
            attributes: YAML 属性字典
            body: Markdown 正文

        Returns:
            格式化的 frontmatter 字符串
        """
        yaml_content = yaml.dump(attributes, allow_unicode=True, sort_keys=False)
        return f"---\n{yaml_content}---\n{body}"

    # ==================== Markdown 内容生成与解析 ====================

    def _generate_skill_markdown_content(self, skill: Skill) -> str:
        """生成 SKILL.md 的 Markdown 正文内容

        Args:
            skill: 技能对象

        Returns:
            Markdown 格式的字符串
        """
        # 获取元数据中的内容
        routing = skill.metadata.get("routing", {})
        decision_table = skill.metadata.get("decision_table", [])
        applicable = skill.metadata.get("applicable_scenarios", "待补充")
        not_applicable = skill.metadata.get("not_applicable_scenarios", "待补充")
        best_practices_do = skill.metadata.get("best_practices_do", "待补充")
        best_practices_dont = skill.metadata.get("best_practices_dont", "待补充")

        # 生成快速决策表
        decision_table_md = self._format_decision_table(decision_table)

        # 生成执行步骤
        steps_md = "\n".join(
            f"{i+1}. **{step}**"
            for i, step in enumerate(skill.workflow.steps)
        ) if skill.workflow.steps else "待补充"

        return f"""# {skill.name}

{skill.description}

## 适用场景

{applicable}

## 不适用场景

{not_applicable}

---

## ⚡ 快速决策表

{decision_table_md}

---

# 工作流程 (Workflow)

## 执行步骤

{steps_md}

---

# 标准操作流程 (SOP)

{skill.workflow.sop or "待补充"}

---

# 最佳实践 (Best Practices)

## DO's ✅

{best_practices_do}

## DON'Ts ❌

{best_practices_dont}

---

# 变更历史 (Evolution Trail)

详细变更历史请参见 `evolution.log`

| 版本 | 日期 | 变更摘要 |
|------|------|---------|
| {skill.metadata.get('version', '1.0.0')} | {skill.updated_at.strftime('%Y-%m-%d')} | 见 evolution.log |

---

# 实现细节 (Implementation)

## Prompt 模板

参见 `impl/prompt.txt`

## 代码实现

参见 `impl/code.py`（可选）

## 测试用例

参见 `impl/test.py`（可选）
"""

    def _format_decision_table(self, decision_table: List[Dict[str, Any]]) -> str:
        """格式化快速决策表

        Args:
            decision_table: 决策表数据，每项包含 condition, action, priority, note

        Returns:
            Markdown 表格字符串
        """
        if not decision_table:
            return """| 条件 | 行动 | 优先级 | 备注 |
|------|------|--------|------|
| 待补充 | 待补充 | 待补充 | 待补充 |"""

        rows = []
        for item in decision_table:
            condition = item.get("condition", "待补充")
            action = item.get("action", "待补充")
            priority = item.get("priority", "中")
            note = item.get("note", "")
            rows.append(f"| {condition} | {action} | {priority} | {note} |")

        header = "| 条件 | 行动 | 优先级 | 备注 |"
        separator = "|------|------|--------|------|"

        return "\n".join([header, separator] + rows)

    def _extract_steps_from_markdown(self, content: str) -> List[str]:
        """从 Markdown 内容提取执行步骤

        Args:
            content: Markdown 正文内容

        Returns:
            步骤列表
        """
        lines = content.split("\n")
        steps = []
        in_section = False

        for line in lines:
            # 查找"执行步骤"标题
            if "执行步骤" in line and line.startswith("#"):
                in_section = True
                continue

            # 提取列表项
            if in_section and line.strip():
                # 匹配 "1. 步骤" 或 "- 步骤" 格式
                line_stripped = line.strip()
                if line_stripped.startswith(("- ", "* ", "• ")):
                    step_text = line_stripped[2:].strip()
                    # 去除可能的 ** 加粗
                    step_text = step_text.replace("**", "").strip()
                    if step_text and not step_text.startswith("#"):
                        steps.append(step_text)
                elif line_stripped[0].isdigit() and ". " in line_stripped[:10]:
                    step_text = line_stripped.split(". ", 1)[1].strip()
                    step_text = step_text.replace("**", "").strip()
                    if step_text:
                        steps.append(step_text)
                elif line_stripped.startswith("#"):
                    # 遇到下一个标题，停止
                    break

        return steps

    def _extract_sop_from_markdown(self, content: str) -> str:
        """从 Markdown 内容提取标准操作流程

        Args:
            content: Markdown 正文内容

        Returns:
            SOP 文本内容
        """
        lines = content.split("\n")
        sop_lines = []
        in_section = False
        found_title = False

        for line in lines:
            # 查找"标准操作流程"或"SOP"标题
            if ("标准操作流程" in line or "SOP" in line) and line.startswith("#"):
                in_section = True
                found_title = True
                continue

            # 收集内容直到下一个同级或更高级标题
            if in_section:
                if line.startswith("#") and "SOP" not in line and "标准操作流程" not in line:
                    break
                if found_title and line.strip():
                    sop_lines.append(line)

        return "\n".join(sop_lines).strip()

    # ==================== 实现文件管理 ====================

    async def _write_implementation(self, impl_dir: Path, skill: Skill) -> None:
        """写入实现文件

        Args:
            impl_dir: impl 目录路径
            skill: 技能对象
        """
        impl_dir.mkdir(parents=True, exist_ok=True)

        # 写入 prompt.txt
        prompt_path = impl_dir / "prompt.txt"
        prompt_content = skill.metadata.get("prompt_template", "")
        async with aiofiles.open(prompt_path, "w", encoding="utf-8") as f:
            await f.write(prompt_content)

        # 可选：写入 code.py
        if "code_implementation" in skill.metadata:
            code_path = impl_dir / "code.py"
            async with aiofiles.open(code_path, "w", encoding="utf-8") as f:
                await f.write(skill.metadata["code_implementation"])

        # 可选：写入 test.py
        if "test_code" in skill.metadata:
            test_path = impl_dir / "test.py"
            async with aiofiles.open(test_path, "w", encoding="utf-8") as f:
                await f.write(skill.metadata["test_code"])

    # ==================== 技能容器管理 (公共 API) ====================

    async def save_skill_container(
        self,
        skill: Skill,
        change_summary: Optional[str] = None
    ) -> str:
        """保存技能容器到文件系统

        策略：先写文件，确保数据安全后再更新索引

        Args:
            skill: 技能对象
            change_summary: 变更摘要（可选），首次保存可为 None

        Returns:
            技能容器路径 (字符串)
        """
        # 1. 确定分类
        category = skill.metadata.get("category", "uncategorized")

        # 2. 创建技能容器目录
        skill_dir = self.skills_dir / category / skill.skill_id
        skill_dir.mkdir(parents=True, exist_ok=True)

        # 3. 生成 SKILL.md (E.S.P 格式) - 先写核心文件
        await self._write_skill_md(skill_dir, skill)

        # 4. 创建 impl 目录结构并写入实现文件
        impl_dir = skill_dir / "impl"
        await self._write_implementation(impl_dir, skill)

        # 5. 写入 RULES.md (高内聚规则)
        await self._write_rules_md(skill_dir, skill)

        # 6. 追加 evolution.log
        await self._append_evolution_log(
            skill_dir,
            skill,
            change_summary=change_summary or "初始创建"
        )

        # 7. 最后更新索引（确保文件已写完再更新）
        await self._update_index(skill)

        return str(skill_dir)

    async def get_skill_container(self, skill_id: str) -> Optional[Skill]:
        """从文件系统读取技能容器

        Args:
            skill_id: 技能 ID（支持直接 ID 或 category/skill_id 路径）

        Returns:
            Skill 对象，如果不存在则返回 None
        """
        # 1. 首先尝试从索引查找
        index = await self._load_index()
        skill_info = index.get("skills", {}).get(skill_id)

        skill_path = None
        if skill_info:
            # 索引中存储的是目录路径，需要加上 SKILL.md
            skill_path = self.kb_dir / skill_info["path"] / "SKILL.md"
        else:
            # 2. 回退：尝试直接扫描目录查找
            for category_dir in self.skills_dir.iterdir():
                if not category_dir.is_dir():
                    continue
                candidate_path = category_dir / skill_id / "SKILL.md"
                if candidate_path.exists():
                    skill_path = candidate_path
                    break

        if not skill_path:
            return None

        # 3. 读取 SKILL.md
        if not skill_path.exists():
            return None

        return await self._parse_skill_md(skill_path)

    async def list_skill_containers(
        self,
        category: Optional[str] = None,
        limit: int = 100,
        load_full: bool = False  # 是否加载完整技能（带工作流程）
    ) -> List[Skill]:
        """列出技能容器

        Args:
            category: 可选分类过滤
            limit: 最大返回数量
            load_full: 是否加载完整技能（False=仅索引信息，True=完整 SKILL.md）

        Returns:
            Skill 对象列表，按更新时间倒序
        """
        index = await self._load_index()

        if not load_full:
            # 快速模式：仅从索引返回信息（不读取文件）
            skills = []
            for skill_id, skill_info in index.get("skills", {}).items():
                if category and skill_info.get("category") != category:
                    continue

                # 创建轻量级 Skill 对象（仅元数据）
                skill = Skill(
                    skill_id=skill_id,
                    name=skill_info.get("name", ""),
                    description=skill_info.get("description", ""),
                    source_sessions=[],
                    confidence=skill_info.get("confidence", 0.5),
                    created_at=datetime.fromisoformat(skill_info.get("created_at", datetime.now().isoformat())),
                    updated_at=datetime.fromisoformat(skill_info.get("updated_at", datetime.now().isoformat())),
                    metadata={
                        "category": skill_info.get("category", "uncategorized"),
                        "version": skill_info.get("version", "1.0.0"),
                        "tags": skill_info.get("tags", []),
                    }
                )
                skills.append(skill)

            # 按更新时间倒序排序
            skills.sort(key=lambda x: x.updated_at, reverse=True)
            return skills[:limit]

        # 完整模式：加载完整技能（需要读取文件）
        skills = []
        for skill_id, skill_info in index.get("skills", {}).items():
            if category and skill_info.get("category") != category:
                continue

            skill = await self.get_skill_container(skill_id)
            if skill:
                skills.append(skill)

        skills.sort(key=lambda x: x.updated_at, reverse=True)
        return skills[:limit]
        return skills[:limit]

    async def search_skill_containers(
        self,
        query: str,
        category: Optional[str] = None,
        top_k: int = 5
    ) -> List[Skill]:
        """搜索技能容器（多维度匹配）

        Args:
            query: 搜索查询
            category: 可选分类过滤
            top_k: 返回前 K 个结果

        Returns:
            Skill 对象列表，按相关性分数排序
        """
        index = await self._load_index()
        results = []
        query_lower = query.lower()

        for skill_id, skill_info in index.get("skills", {}).items():
            # 分类过滤
            if category and skill_info.get("category") != category:
                continue

            # 多维度匹配打分
            score = 0

            # 名称匹配 (权重: 10) - 查询包含名称
            name = skill_info.get("name", "").lower()
            if query_lower in name or name in query_lower:
                score += 10

            # 描述匹配 (权重: 5) - 查询包含描述关键词
            desc = skill_info.get("description", "").lower()
            if query_lower in desc or desc in query_lower:
                score += 5

            # 标签匹配 (权重: 3) - 查询包含标签
            for tag in skill_info.get("tags", []):
                if query_lower in tag.lower() or tag.lower() in query_lower:
                    score += 3

            # 路由关键词匹配 (权重: 8) - 查询包含触发关键词
            for keyword in skill_info.get("trigger_keywords", []):
                if query_lower in keyword.lower() or keyword.lower() in query_lower:
                    score += 8

            # 只有分数 > 0 才加入结果
            if score > 0:
                skill = await self.get_skill_container(skill_id)
                if skill:
                    skill.metadata["search_score"] = score
                    results.append(skill)

        # 按搜索分数排序
        results.sort(key=lambda x: x.metadata.get("search_score", 0), reverse=True)
        return results[:top_k]

    async def update_skill_container(
        self,
        skill_id: str,
        updates: Dict[str, Any],
        change_summary: str
    ) -> Optional[Skill]:
        """更新技能容器

        Args:
            skill_id: 技能 ID
            updates: 要更新的字段字典
            change_summary: 变更摘要（必填），将写入 evolution.log

        Returns:
            更新后的 Skill 对象，如果技能不存在则返回 None
        """
        # 1. 获取现有技能
        skill = await self.get_skill_container(skill_id)
        if not skill:
            return None

        # 2. 应用更新
        for key, value in updates.items():
            if hasattr(skill, key):
                setattr(skill, key, value)
            else:
                skill.metadata[key] = value

        # 3. 更新时间戳
        skill.updated_at = datetime.now()

        # 4. 版本号自增（如果指定）
        if "version_increment" in updates:
            skill.metadata["version"] = self._increment_version(
                skill.metadata.get("version", "1.0.0"),
                updates["version_increment"]
            )

        # 5. 重新保存（传入 change_summary）
        await self.save_skill_container(skill, change_summary=change_summary)

        return skill

    async def delete_skill_container(self, skill_id: str) -> bool:
        """删除技能容器

        Args:
            skill_id: 要删除的技能 ID

        Returns:
            是否成功删除
        """
        # 1. 从索引获取信息
        index = await self._load_index()
        skill_info = index.get("skills", {}).get(skill_id)

        if not skill_info:
            return False

        # 2. 删除整个技能容器目录
        skill_dir = self.kb_dir / skill_info["path"]
        if skill_dir.exists():
            import shutil
            shutil.rmtree(skill_dir)

        # 3. 从索引中移除
        await self._remove_from_index(skill_id)

        return True

    # ==================== 辅助方法 ====================

    def _increment_version(self, version: str, increment_type: str = "patch") -> str:
        """语义化版本号自增

        Args:
            version: 当前版本号 (格式: "major.minor.patch")
            increment_type: 自增类型 ("major", "minor", "patch")

        Returns:
            新版本号
        """
        try:
            major, minor, patch = map(int, version.split("."))
        except (ValueError, AttributeError):
            # 如果版本号格式不正确，默认为 1.0.0
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

        return f"{major}.{minor}.{patch}"

    # ==================== 变更日志管理 ====================

    async def _append_evolution_log(
        self,
        skill_dir: Path,
        skill: Skill,
        change_summary: str
    ) -> None:
        """追加变更日志

        Args:
            skill_dir: 技能容器目录
            skill: 技能对象
            change_summary: 变更摘要

        日志格式:
            [时间戳] v{version} - {change_summary}
              Source: {source_session}
        """
        log_path = skill_dir / "evolution.log"
        version = skill.metadata.get("version", "1.0.0")
        source = skill.source_sessions[-1] if skill.source_sessions else "unknown"

        log_entry = (
            f"[{datetime.now().isoformat()}] "
            f"v{version} - {change_summary}\n"
            f"  Source: {source}\n"
        )

        async with aiofiles.open(log_path, "a", encoding="utf-8") as f:
            await f.write(log_entry)

    # ==================== 技能规则管理 (RULES.md) ====================

    async def _write_rules_md(self, skill_dir: Path, skill: Skill) -> None:
        """写入技能专属规则文件 RULES.md (高内聚)

        Args:
            skill_dir: 技能容器目录
            skill: 技能对象
        """
        rules_path = skill_dir / "RULES.md"

        # 从 metadata 获取规则
        must_do = skill.metadata.get("rules_must_do", [])
        dont = skill.metadata.get("rules_dont", [])

        content = f"""# {skill.name} - 技能规则

本规则文件与技能紧密耦合，定义使用该技能时必须遵守的约束条件。

---

## Must-Do (必须遵守)

{self._format_rules_list(must_do, "无特殊要求")}

---

## Don't (禁止行为)

{self._format_rules_list(dont, "无特殊限制")}

---

*本规则文件与技能容器高内聚，随技能一同版本控制。*
"""

        async with aiofiles.open(rules_path, "w", encoding="utf-8") as f:
            await f.write(content)

    def _format_rules_list(self, rules: List[str], fallback: str) -> str:
        """格式化规则列表

        Args:
            rules: 规则列表
            fallback: 当列表为空时的默认文本

        Returns:
            格式化后的规则字符串
        """
        if not rules:
            return fallback

        return "\n".join(f"- {rule}" for rule in rules)

    # ==================== 变更历史查询 ====================

    async def get_evolution_log(self, skill_id: str) -> List[Dict[str, str]]:
        """获取技能的变更历史

        Args:
            skill_id: 技能 ID

        Returns:
            变更历史记录列表，每项包含 timestamp, version, summary, source
        """
        # 1. 从索引获取技能路径
        index = await self._load_index()
        skill_info = index.get("skills", {}).get(skill_id)

        if not skill_info:
            return []

        # 2. 读取 evolution.log
        skill_dir = self.kb_dir / skill_info["path"]
        log_path = skill_dir / "evolution.log"

        if not log_path.exists():
            return []

        # 3. 解析日志文件
        entries = []
        async with aiofiles.open(log_path, "r", encoding="utf-8") as f:
            content = await f.read()

        for line in content.split("\n"):
            line = line.strip()
            if not line:
                continue

            # 解析格式: [timestamp] v{version} - {summary}
            if line.startswith("["):
                # 提取时间戳
                timestamp_end = line.find("]")
                timestamp = line[1:timestamp_end]

                # 提取版本和摘要
                remainder = line[timestamp_end + 1:].strip()
                if remainder.startswith("v"):
                    version_end = remainder.find(" - ")
                    version = remainder[1:version_end]
                    summary = remainder[version_end + 3:].strip()

                    entries.append({
                        "timestamp": timestamp,
                        "version": version,
                        "summary": summary,
                        "source": ""  # 将在下一行处理
                    })
            elif line.startswith("Source:") and entries:
                # 更新最后一个条目的 source
                entries[-1]["source"] = line.split("Source:", 1)[1].strip()

        return entries

    async def export_skill_markdown(self, skill_id: str) -> Optional[str]:
        """导出技能为 E.S.P Markdown 格式

        Args:
            skill_id: 技能 ID

        Returns:
            Markdown 字符串，如果技能不存在则返回 None
        """
        # 1. 从索引获取技能路径
        index = await self._load_index()
        skill_info = index.get("skills", {}).get(skill_id)

        if not skill_info:
            return None

        # 2. 读取 SKILL.md
        skill_dir = self.kb_dir / skill_info["path"]
        skill_md_path = skill_dir / "SKILL.md"

        if not skill_md_path.exists():
            return None

        async with aiofiles.open(skill_md_path, "r", encoding="utf-8") as f:
            return await f.read()

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
            导入的 Skill 对象，如果解析失败则返回 None
        """
        try:
            # 解析 Markdown - 使用新版 frontmatter API
            result = frontmatter.Frontmatter.read(markdown_content)
            metadata = dict(result.get("attributes", {}))

            # 覆盖 skill_id（如果提供）
            if skill_id:
                metadata["skill_id"] = skill_id

            # 提取工作流程
            body = result.get("body", "")
            steps = self._extract_steps_from_markdown(body)
            sop = self._extract_sop_from_markdown(body)

            # 构造 Skill 对象
            skill = Skill(
                skill_id=metadata["skill_id"],
                name=metadata["name"],
                description=metadata.get("description", ""),
                workflow=Workflow(steps=steps, sop=sop),
                source_sessions=metadata.get("source_sessions", []),
                confidence=metadata.get("confidence", 0.5),
                created_at=datetime.fromisoformat(metadata["created_at"]),
                updated_at=datetime.fromisoformat(metadata["updated_at"]),
                metadata=metadata
            )

            # 保存技能
            await self.save_skill_container(skill, change_summary="从 Markdown 导入")

            return skill

        except Exception as e:
            print(f"导入技能失败: {e}")
            return None

    # ==================== 索引重建 ====================

    async def rebuild_index(self) -> Dict[str, Any]:
        """重建技能索引

        扫描 skills/ 目录，重新构建 _index.json

        Returns:
            重建结果摘要，包含 total_skills, successful, failed
        """
        result = {
            "total_skills": 0,
            "successful": 0,
            "failed": 0,
            "failed_skills": []
        }

        # 1. 创建新索引
        new_index = {
            "skills": {},
            "rules": {},
            "last_updated": datetime.now().isoformat(),
            "version": "2.0.0"
        }

        # 2. 遍历所有分类目录
        if not self.skills_dir.exists():
            await self._save_index(new_index)
            return result

        for category_dir in self.skills_dir.iterdir():
            if not category_dir.is_dir():
                continue

            category = category_dir.name

            # 3. 遍历该分类下的所有技能目录
            for skill_dir in category_dir.iterdir():
                if not skill_dir.is_dir():
                    continue

                skill_md_path = skill_dir / "SKILL.md"

                if not skill_md_path.exists():
                    result["failed"] += 1
                    result["failed_skills"].append({
                        "skill_id": skill_dir.name,
                        "reason": "SKILL.md 不存在"
                    })
                    continue

                try:
                    # 解析 SKILL.md
                    skill = await self._parse_skill_md(skill_md_path)

                    if skill:
                        # 添加到索引
                        relative_path = f"skills/{category}/{skill.skill_id}"
                        routing = skill.metadata.get("routing", {})

                        new_index["skills"][skill.skill_id] = {
                            "name": skill.name,
                            "description": skill.description,
                            "category": category,
                            "path": relative_path,
                            "version": skill.metadata.get("version", "1.0.0"),
                            "tags": skill.metadata.get("tags", []),
                            "trigger_keywords": routing.get("trigger_keywords", []),
                            "confidence": skill.confidence,
                            "created_at": skill.created_at.isoformat(),
                            "updated_at": skill.updated_at.isoformat(),
                        }

                        result["successful"] += 1
                    else:
                        result["failed"] += 1
                        result["failed_skills"].append({
                            "skill_id": skill_dir.name,
                            "reason": "解析失败"
                        })

                except Exception as e:
                    result["failed"] += 1
                    result["failed_skills"].append({
                        "skill_id": skill_dir.name,
                        "reason": str(e)
                    })

        result["total_skills"] = result["successful"] + result["failed"]

        # 4. 保存新索引
        await self._save_index(new_index)

        return result

    # ==================== 版本管理 ====================

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
            更新后的 Skill 对象，如果技能不存在则返回 None
        """
        # 1. 获取现有技能
        skill = await self.get_skill_container(skill_id)
        if not skill:
            return None

        # 2. 获取当前版本并计算新版本
        current_version = skill.metadata.get("version", "1.0.0")
        new_version = self._increment_version(current_version, increment_type)

        # 3. 更新版本号
        skill.metadata["version"] = new_version
        skill.updated_at = datetime.now()

        # 4. 保存技能（传入变更摘要）
        summary = change_summary or f"版本更新: {current_version} → {new_version}"
        await self.save_skill_container(skill, change_summary=summary)

        return skill
