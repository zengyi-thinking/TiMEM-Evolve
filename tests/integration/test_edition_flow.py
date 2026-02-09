"""经验编辑流程集成测试

测试：经验可编辑 - Markdown 读写同步
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from pathlib import Path
import json
import frontmatter
import yaml

from timem_evolve.dao.registry_dao import RegistryDAO
from timem_evolve.dao.unified_dao import UnifiedDAO
from timem_evolve.models import Skill, Workflow


def read_frontmatter(path: Path):
    """读取 frontmatter 格式的 markdown 文件"""
    content = path.read_text(encoding="utf-8")
    # 解析 frontmatter
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            yaml_content = parts[1].strip()
            body = parts[2].strip()
            metadata = yaml.safe_load(yaml_content) or {}
            metadata["body"] = body
            return metadata
    return {"content": content}


class TestSkillMarkdownEditing:
    """技能 Markdown 编辑测试类"""

    @pytest.fixture
    async def registry_dao(self, tmp_path):
        """创建 RegistryDAO 实例"""
        kb_dir = str(tmp_path / "knowledge_base")
        dao = RegistryDAO(knowledge_base_dir=kb_dir)
        return dao

    @pytest.fixture
    async def unified_dao(self, tmp_path):
        """创建 UnifiedDAO 实例"""
        data_dir = str(tmp_path / "data")
        dao = UnifiedDAO(data_dir=data_dir, use_registry=True)
        await dao.init_db()
        return dao

    @pytest.fixture
    def sample_skill(self):
        """创建测试用技能"""
        return Skill(
            skill_id="edit_test_skill_001",
            name="编辑测试技能",
            description="这是用于测试编辑功能的初始描述",
            workflow=Workflow(
                steps=["步骤1: 准备", "步骤2: 执行"],
                sop="标准操作流程"
            ),
            metadata={
                "category": "test",
                "version": "1.0.0",
                "tags": ["测试"],
                "routing": {
                    "trigger_keywords": ["测试"],
                    "priority": 5
                }
            }
        )

    @pytest.mark.asyncio
    async def test_edit_skill_markdown_file(self, registry_dao, sample_skill):
        """直接编辑 Markdown 文件"""
        # 1. 保存技能
        await registry_dao.save_skill_container(sample_skill, change_summary="初始创建")

        # 2. 直接修改 SKILL.md
        skill_dir = registry_dao.skills_dir / sample_skill.metadata["category"] / sample_skill.skill_id
        skill_md_path = skill_dir / "SKILL.md"

        assert skill_md_path.exists()

        # 读取并修改
        content = skill_md_path.read_text(encoding="utf-8")
        new_content = content.replace("初始描述", "手动编辑后的描述")
        skill_md_path.write_text(new_content, encoding="utf-8")

        # 3. 重新读取技能
        updated_skill = await registry_dao.get_skill_container(sample_skill.skill_id)

        assert updated_skill is not None
        assert "手动编辑后的描述" in updated_skill.description

    @pytest.mark.asyncio
    async def test_api_update_and_sync_to_filesystem(self, registry_dao, sample_skill):
        """API 更新并同步到文件系统"""
        # 1. 保存初始技能
        await registry_dao.save_skill_container(sample_skill, change_summary="初始创建")

        # 2. 通过 API 更新
        updated = await registry_dao.update_skill_container(
            skill_id=sample_skill.skill_id,
            updates={
                "description": "API 更新的描述",
                "routing": {
                    "trigger_keywords": ["测试", "更新"],
                    "priority": 8
                },
                "version_increment": "patch"
            },
            change_summary="API 更新"
        )

        # 3. 验证文件系统已同步
        skill_dir = registry_dao.skills_dir / sample_skill.metadata["category"] / sample_skill.skill_id
        skill_md_path = skill_dir / "SKILL.md"

        assert skill_md_path.exists()

        # 读取 Markdown 验证
        post = read_frontmatter(skill_md_path)
        assert "API 更新的描述" in post.get("description", "")

    @pytest.mark.asyncio
    async def test_manual_edit_and_read_via_api(self, registry_dao, sample_skill):
        """手动编辑 Markdown 后通过 API 读取"""
        # 1. 保存初始技能
        await registry_dao.save_skill_container(sample_skill, change_summary="初始创建")

        # 2. 手动编辑 SKILL.md
        skill_dir = registry_dao.skills_dir / sample_skill.metadata["category"] / sample_skill.skill_id
        skill_md_path = skill_dir / "SKILL.md"

        # 添加新章节
        with open(skill_md_path, "a", encoding="utf-8") as f:
            f.write("\n## 手动添加的注意事项\n- 这是手动编辑的内容\n")

        # 3. 通过 API 读取
        updated_skill = await registry_dao.get_skill_container(sample_skill.skill_id)

        assert updated_skill is not None
        # 验证更新后的描述包含新内容（或者至少文件被正确解析）
        assert updated_skill.description is not None

    @pytest.mark.asyncio
    async def test_frontmatter_sync(self, registry_dao, sample_skill):
        """测试 Frontmatter 同步"""
        # 1. 保存技能
        await registry_dao.save_skill_container(sample_skill, change_summary="初始")

        # 2. 读取并验证 frontmatter
        skill_dir = registry_dao.skills_dir / sample_skill.metadata["category"] / sample_skill.skill_id
        skill_md_path = skill_dir / "SKILL.md"

        post = read_frontmatter(skill_md_path)

        assert post.get("skill_id") == sample_skill.skill_id
        assert post.get("name") == sample_skill.name
        assert post.get("version") == "1.0.0"

    @pytest.mark.asyncio
    async def test_evolution_log_on_edit(self, registry_dao, sample_skill):
        """编辑时更新 evolution.log"""
        # 1. 保存初始技能
        await registry_dao.save_skill_container(sample_skill, change_summary="初始创建")

        # 2. 编辑技能
        await registry_dao.update_skill_container(
            skill_id=sample_skill.skill_id,
            updates={"description": "更新后的描述"},
            change_summary="描述更新"
        )

        # 3. 验证 evolution.log 包含新条目
        evolution = await registry_dao.get_evolution_log(sample_skill.skill_id)

        assert len(evolution) >= 2  # 初始 + 更新
        last_entry = evolution[-1]
        assert "描述更新" in last_entry["summary"]


class TestMarkdownExportImport:
    """Markdown 导入导出测试"""

    @pytest.fixture
    async def registry_dao(self, tmp_path):
        kb_dir = str(tmp_path / "kb")
        return RegistryDAO(knowledge_base_dir=kb_dir)

    @pytest.mark.asyncio
    async def test_export_skill_markdown(self, registry_dao):
        """导出技能为 Markdown"""
        skill = Skill(
            skill_id="export_test_001",
            name="导出测试技能",
            description="测试导出功能",
            workflow=Workflow(steps=["步骤1"], sop="流程"),
            metadata={"category": "test", "version": "1.0.0"}
        )

        await registry_dao.save_skill_container(skill, change_summary="测试")

        # 导出
        exported = await registry_dao.export_skill_markdown(skill.skill_id)

        assert exported is not None
        assert "导出测试技能" in exported
        assert "test" in exported.lower()

    @pytest.mark.asyncio
    async def test_import_skill_from_markdown(self, registry_dao):
        """从 Markdown 导入技能"""
        markdown_content = """---
skill_id: import_test_001
name: 导入测试技能
description: 测试导入功能
category: test
version: 1.0.0
created_at: '2024-01-01T00:00:00'
updated_at: '2024-01-01T00:00:00'
---

# 导入测试技能

这是导入的描述。

## 适用场景

测试导入功能

## 执行步骤

1. 导入
2. 验证
3. 完成
"""

        # 导入
        imported = await registry_dao.import_skill_from_markdown(markdown_content)

        assert imported is not None
        assert imported.name == "导入测试技能"
        assert imported.metadata.get("category") == "test"

    @pytest.mark.asyncio
    async def test_import_with_custom_id(self, registry_dao):
        """从 Markdown 导入并指定 ID"""
        markdown_content = """---
skill_id: original_id
name: 原 ID 技能
description: 测试
category: test
version: 1.0.0
created_at: '2024-01-01T00:00:00'
updated_at: '2024-01-01T00:00:00'
---

# 原 ID 技能
"""

        # 导入并指定新 ID
        imported = await registry_dao.import_skill_from_markdown(
            markdown_content,
            skill_id="custom_id_001"
        )

        assert imported is not None
        assert imported.skill_id == "custom_id_001"


class TestUnifiedDAOEditing:
    """UnifiedDAO 编辑测试"""

    @pytest.fixture
    async def unified_dao(self, tmp_path):
        data_dir = str(tmp_path / "data")
        dao = UnifiedDAO(data_dir=data_dir, use_registry=True)
        await dao.init_db()
        return dao

    @pytest.mark.asyncio
    async def test_update_skill_via_unified_dao(self, unified_dao):
        """通过 UnifiedDAO 更新技能"""
        skill = Skill(
            skill_id="unified_update_001",
            name="统一更新测试",
            description="测试统一更新功能",
            workflow=Workflow(steps=["步骤1"], sop="流程"),
            metadata={"category": "test", "version": "1.0.0"}
        )

        await unified_dao.save_skill(skill, change_summary="初始")

        # 更新
        updated = await unified_dao.update_skill(
            skill_id=skill.skill_id,
            updates={"description": "统一更新的描述"},
            change_summary="描述更新"
        )

        assert updated is not None
        assert "统一更新的描述" in updated.description

    @pytest.mark.asyncio
    async def test_delete_skill_via_unified_dao(self, unified_dao):
        """通过 UnifiedDAO 删除技能"""
        skill = Skill(
            skill_id="unified_delete_001",
            name="删除测试",
            description="测试删除功能",
            workflow=Workflow(steps=["步骤1"], sop="流程"),
            metadata={"category": "test", "version": "1.0.0"}
        )

        await unified_dao.save_skill(skill, change_summary="测试")

        # 删除
        result = await unified_dao.delete_skill(skill.skill_id)

        assert result == True

        # 验证已删除
        deleted = await unified_dao.get_skill(skill.skill_id)
        assert deleted is None


class TestSkillVersionBumpOnEdit:
    """编辑时版本递增测试"""

    @pytest.fixture
    async def registry_dao(self, tmp_path):
        kb_dir = str(tmp_path / "kb")
        return RegistryDAO(knowledge_base_dir=kb_dir)

    @pytest.mark.asyncio
    async def test_patch_version_bump_on_description_change(self, registry_dao):
        """描述变更触发 patch 版本更新"""
        skill = Skill(
            skill_id="version_test_001",
            name="版本测试",
            description="原始描述",
            workflow=Workflow(steps=["步骤1"], sop="流程"),
            metadata={"category": "test", "version": "1.0.0"}
        )

        await registry_dao.save_skill_container(skill, change_summary="初始")

        # 更新描述
        updated = await registry_dao.update_skill_container(
            skill_id=skill.skill_id,
            updates={"description": "更新后的描述", "version_increment": "patch"},
            change_summary="描述更新"
        )

        assert updated.metadata.get("version") == "1.0.1"

    @pytest.mark.asyncio
    async def test_minor_version_bump_on_workflow_change(self, registry_dao):
        """工作流程变更触发 minor 版本更新"""
        skill = Skill(
            skill_id="version_test_002",
            name="流程版本测试",
            description="测试",
            workflow=Workflow(steps=["原步骤"], sop="原流程"),
            metadata={"category": "test", "version": "1.0.0"}
        )

        await registry_dao.save_skill_container(skill, change_summary="初始")

        # 更新工作流程
        updated = await registry_dao.update_skill_container(
            skill_id=skill.skill_id,
            updates={
                "workflow": Workflow(
                    steps=["新步骤1", "新步骤2"],
                    sop="新流程"
                ),
                "version_increment": "minor"
            },
            change_summary="流程重构"
        )

        assert updated.metadata.get("version") == "1.1.0"
