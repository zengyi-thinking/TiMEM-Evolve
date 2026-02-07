#!/usr/bin/env python3
"""TiMEM-Evolve v1.0 -> v2.0 数据迁移脚本

将 skills.json (v1.0 JSON 格式) 迁移到 M.S.F.S (v2.0 文件系统格式)

特性:
- 安全备份：自动备份原始 skills.json
- 增量迁移：支持跳过已迁移的技能
- 回滚支持：保留原始数据，可随时恢复
- 详细日志：记录每个技能的迁移状态

使用方式:
    # 直接运行（使用默认配置）
    python scripts/migrate_v1_to_v2.py

    # 指定数据目录
    python scripts/migrate_v1_to_v2.py --data-dir ./data

    # 预览模式（不实际执行）
    python scripts/migrate_v1_to_v2.py --dry-run

    # 强制重新迁移所有技能
    python scripts/migrate_v1_to_v2.py --force

环境变量:
    USE_SKILL_REGISTRY=true  # 确保启用 M.S.F.S
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


def add_project_root_to_path():
    """将项目根目录添加到 Python 路径"""
    project_root = Path(__file__).parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))


add_project_root_to_path()

from timem_evolve.dao import UnifiedDAO
from timem_evolve.models import Skill, SkillRouting, Workflow


class MigrationLogger:
    """迁移日志记录器"""

    def __init__(self, log_file: str):
        self.log_file = Path(log_file)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        self.logs: List[Dict[str, Any]] = []

    def log(self, level: str, skill_id: str, message: str, details: Dict[str, Any] = None):
        """记录日志"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "skill_id": skill_id,
            "message": message,
            "details": details or {},
        }
        self.logs.append(entry)

        # 控制台输出
        status_icon = {"INFO": "ℹ️", "SUCCESS": "✅", "WARNING": "⚠️", "ERROR": "❌"}.get(level, "•")
        print(f"{status_icon} [{skill_id[:8]}...] {message}")

    def save(self):
        """保存日志到文件"""
        with open(self.log_file, "w", encoding="utf-8") as f:
            json.dump(self.logs, f, indent=2, ensure_ascii=False)

    def summary(self) -> Dict[str, int]:
        """生成日志摘要"""
        summary = {"INFO": 0, "SUCCESS": 0, "WARNING": 0, "ERROR": 0}
        for log in self.logs:
            summary[log["level"]] += 1
        return summary


class V1ToV2Migrator:
    """v1.0 -> v2.0 数据迁移器"""

    def __init__(
        self,
        data_dir: str = "./data",
        dry_run: bool = False,
        force: bool = False
    ):
        self.data_dir = Path(data_dir)
        self.skills_json_path = self.data_dir / "skills.json"
        self.backup_path = self.data_dir / "skills.json.v1.backup"
        self.log_path = self.data_dir / "migration_logs" / f"migration_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        self.dry_run = dry_run
        self.force = force

        self.logger = MigrationLogger(str(self.log_path))

    def validate_source(self) -> bool:
        """验证源文件是否存在"""
        if not self.skills_json_path.exists():
            self.logger.log("ERROR", "system", f"源文件不存在: {self.skills_json_path}")
            return False

        try:
            data = json.loads(self.skills_json_path.read_text(encoding="utf-8"))
            if not isinstance(data, list):
                self.logger.log("ERROR", "system", f"源文件格式错误: 应为列表，实际为 {type(data).__name__}")
                return False

            self.logger.log("INFO", "system", f"源文件验证通过，包含 {len(data)} 个技能")
            return True
        except Exception as e:
            self.logger.log("ERROR", "system", f"源文件解析失败: {e}")
            return False

    def backup_source(self) -> bool:
        """备份源文件"""
        if self.backup_path.exists():
            self.logger.log("INFO", "system", f"备份文件已存在，跳过备份: {self.backup_path}")
            return True

        try:
            import shutil
            shutil.copy2(self.skills_json_path, self.backup_path)
            self.logger.log("SUCCESS", "system", f"备份创建成功: {self.backup_path}")
            return True
        except Exception as e:
            self.logger.log("ERROR", "system", f"备份创建失败: {e}")
            return False

    def load_v1_skills(self) -> List[Dict[str, Any]]:
        """加载 v1.0 技能数据"""
        try:
            data = json.loads(self.skills_json_path.read_text(encoding="utf-8"))
            self.logger.log("INFO", "system", f"成功加载 {len(data)} 个 v1.0 技能")
            return data
        except Exception as e:
            self.logger.log("ERROR", "system", f"加载 v1.0 数据失败: {e}")
            return []

    def convert_to_v2_skill(self, v1_skill: Dict[str, Any]) -> Skill:
        """将 v1.0 技能转换为 v2.0 Skill 对象

        转换映射:
        - skill_id: 保持不变
        - name: 保持不变
        - description: 保持不变
        - workflow: 拆分为 steps 和 sop
        - source_sessions: 保持不变
        - confidence: 保持不变
        - created_at/updated_at: 从 v1 数据保留或使用默认值
        - metadata: 新增 v2.0 扩展字段
        """
        # 提取工作流程
        workflow_data = v1_skill.get("workflow", {})
        if isinstance(workflow_data, dict):
            steps = workflow_data.get("steps", [])
            sop = workflow_data.get("sop", "")
        else:
            steps = []
            sop = str(workflow_data) if workflow_data else ""

        # 构建扩展元数据（v2.0 新增）
        metadata = {
            # E.S.P 基础字段
            "category": self._infer_category(v1_skill),
            "version": "1.0.0",
            "author": "TiMEM-Learner",
            "tags": self._extract_tags_from_name(v1_skill.get("name", "")),

            # 决策表（从描述中提取）
            "decision_table": self._generate_decision_table(v1_skill),

            # 场景描述（默认值）
            "applicable_scenarios": "待补充",
            "not_applicable_scenarios": "待补充",

            # 最佳实践（从 SOP 中提取）
            "best_practices_do": self._extract_best_practices(sop, "do"),
            "best_practices_dont": self._extract_best_practices(sop, "dont"),

            # 规则（空列表）
            "rules_must_do": [],
            "rules_dont": [],

            # 路由配置（从技能名推断）
            "routing": self._generate_routing(v1_skill),

            # 保留 v1.0 的原始 metadata
            "v1_metadata": v1_skill.get("metadata", {}),
        }

        # 时间戳处理
        created_at = datetime.now()
        updated_at = datetime.now()

        if v1_skill.get("created_at"):
            try:
                created_at = datetime.fromisoformat(v1_skill["created_at"])
            except:
                pass
        if v1_skill.get("updated_at"):
            try:
                updated_at = datetime.fromisoformat(v1_skill["updated_at"])
            except:
                pass

        # 构建 Skill 对象
        return Skill(
            skill_id=v1_skill.get("skill_id", ""),
            name=v1_skill.get("name", ""),
            description=v1_skill.get("description", ""),
            workflow=Workflow(steps=steps, sop=sop),
            source_sessions=v1_skill.get("source_sessions", []),
            confidence=v1_skill.get("confidence", 0.5),
            created_at=created_at,
            updated_at=updated_at,
            metadata=metadata
        )

    def _infer_category(self, v1_skill: Dict[str, Any]) -> str:
        """从技能名称或描述推断分类"""
        name = v1_skill.get("name", "").lower()
        description = v1_skill.get("description", "").lower()

        # 关键词映射到分类
        category_keywords = {
            "programming": ["代码", "编程", "debug", "调试", "开发", "重构", "测试"],
            "communication": ["沟通", "对话", "回复", "解释", "说明", "咨询"],
            "analysis": ["分析", "评估", "诊断", "检查", "审核"],
            "search": ["搜索", "检索", "查询", "查找"],
            "writing": ["写作", "文档", "生成", "撰写"],
        }

        text = f"{name} {description}"
        for category, keywords in category_keywords.items():
            if any(keyword in text for keyword in keywords):
                return category

        return "migrated"

    def _extract_tags_from_name(self, name: str) -> List[str]:
        """从技能名称提取标签"""
        tags = []
        name_lower = name.lower()

        # 通用标签
        if "调试" in name_lower or "debug" in name_lower:
            tags.append("debugging")
        if "代码" in name_lower or "code" in name_lower:
            tags.append("programming")
        if "搜索" in name_lower or "search" in name_lower:
            tags.append("search")

        return tags

    def _generate_decision_table(self, v1_skill: Dict[str, Any]) -> List[Dict[str, Any]]:
        """生成快速决策表（默认占位）"""
        return [
            {
                "condition": "相关请求",
                "action": f"使用 {v1_skill.get('name', '本技能')}",
                "priority": "中",
                "note": "从 v1.0 迁移，待人工优化"
            }
        ]

    def _extract_best_practices(self, sop: str, kind: str) -> str:
        """从 SOP 中提取最佳实践"""
        # 简单实现：返回默认占位文本
        if kind == "do":
            return "• 遵循标准操作流程\n• 注意细节和准确性"
        else:
            return "• 避免跳过步骤\n• 不要忽视异常情况"

    def _generate_routing(self, v1_skill: Dict[str, Any]) -> Dict[str, Any]:
        """生成路由配置"""
        name = v1_skill.get("name", "")
        description = v1_skill.get("description", "")

        # 从名称和描述提取关键词
        keywords = []
        for word in name.split():
            if len(word) > 1:
                keywords.append(word)

        return {
            "trigger_keywords": keywords[:5],  # 最多 5 个关键词
            "priority": 5,
            "conditions": []
        }

    async def migrate_skill(self, v1_skill: Dict[str, Any], dao: UnifiedDAO) -> bool:
        """迁移单个技能

        Returns:
            是否成功迁移
        """
        skill_id = v1_skill.get("skill_id", "")

        try:
            # 检查是否已存在
            existing = await dao.get_skill(skill_id)
            if existing and not self.force:
                self.logger.log(
                    "WARNING",
                    skill_id,
                    "技能已存在，跳过迁移（使用 --force 强制覆盖）"
                )
                return False

            # 转换为 v2.0 Skill
            v2_skill = self.convert_to_v2_skill(v1_skill)

            if self.dry_run:
                self.logger.log(
                    "INFO",
                    skill_id,
                    f"[DRY RUN] 将迁移: {v2_skill.name}"
                )
                return True

            # 保存到 UnifiedDAO
            await dao.save_skill(v2_skill, change_summary="v1.0 -> v2.0 迁移")

            self.logger.log(
                "SUCCESS",
                skill_id,
                f"迁移成功: {v2_skill.name} (分类: {v2_skill.category})"
            )
            return True

        except Exception as e:
            self.logger.log("ERROR", skill_id, f"迁移失败: {e}")
            return False

    async def run(self) -> Dict[str, int]:
        """执行迁移

        Returns:
            迁移统计摘要
        """
        self.logger.log("INFO", "system", "=" * 60)
        self.logger.log("INFO", "system", "TiMEM-Evolve v1.0 -> v2.0 数据迁移")
        self.logger.log("INFO", "system", "=" * 60)

        if self.dry_run:
            self.logger.log("INFO", "system", "⚠️ 预览模式：不会实际写入数据")

        # 验证源文件
        if not self.validate_source():
            self.logger.save()
            return {"ERROR": 1}

        # 备份源文件
        if not self.dry_run and not self.backup_source():
            self.logger.save()
            return {"ERROR": 1}

        # 加载 v1.0 数据
        v1_skills = self.load_v1_skills()
        if not v1_skills:
            self.logger.save()
            return {"ERROR": 1}

        # 初始化 UnifiedDAO
        dao = UnifiedDAO(data_dir=str(self.data_dir), use_registry=True)

        self.logger.log("INFO", "system", f"后端配置: {dao.get_backend_info()}")

        # 迁移每个技能
        success_count = 0
        skip_count = 0
        error_count = 0

        for v1_skill in v1_skills:
            skill_id = v1_skill.get("skill_id", "unknown")

            try:
                result = await self.migrate_skill(v1_skill, dao)
                if result:
                    success_count += 1
                else:
                    skip_count += 1
            except Exception as e:
                self.logger.log("ERROR", skill_id, f"迁移异常: {e}")
                error_count += 1

        # 输出摘要
        self.logger.log("INFO", "system", "=" * 60)
        self.logger.log("INFO", "system", "迁移摘要:")
        self.logger.log("INFO", "system", f"  总计: {len(v1_skills)} 个技能")
        self.logger.log("INFO", "system", f"  成功: {success_count} 个")
        self.logger.log("INFO", "system", f"  跳过: {skip_count} 个")
        self.logger.log("INFO", "system", f"  失败: {error_count} 个")
        self.logger.log("INFO", "system", "=" * 60)

        if not self.dry_run:
            self.logger.log("INFO", "system", f"✅ 迁移完成！日志已保存至: {self.log_path}")
            self.logger.log("INFO", "system", f"💾 原始备份位于: {self.backup_path}")
        else:
            self.logger.log("INFO", "system", "⚠️ 预览模式完成，未实际写入数据")

        # 保存日志
        self.logger.save()

        return {
            "SUCCESS": success_count,
            "WARNING": skip_count,
            "ERROR": error_count,
        }


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="TiMEM-Evolve v1.0 -> v2.0 数据迁移脚本"
    )
    parser.add_argument(
        "--data-dir",
        default="./data",
        help="数据目录路径（默认: ./data）"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="预览模式，不实际执行迁移"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="强制覆盖已存在的技能"
    )

    args = parser.parse_args()

    migrator = V1ToV2Migrator(
        data_dir=args.data_dir,
        dry_run=args.dry_run,
        force=args.force
    )

    summary = await migrator.run()

    # 返回退出码
    if summary.get("ERROR", 0) > 0:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
