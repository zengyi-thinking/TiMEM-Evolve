"""技能编辑测试数据集：测试 Markdown 编辑和同步"""
from typing import Dict, Any, List
from dataclasses import dataclass


@dataclass
class EditTestCase:
    """编辑测试用例"""
    skill_id: str
    edit_type: str
    old_value: Any
    new_value: Any
    expected_version_bump: str


EDITION_DATASETS: Dict[str, Dict[str, Any]] = {
    # ========== 描述编辑 ==========
    "update_description": {
        "skill_id": "skill_edit_desc_001",
        "edit_type": "description",
        "old_value": "旧的技能描述",
        "new_value": "更新后的技能描述，这是一个更好的描述",
        "expected_version_bump": "patch"
    },

    "major_description_change": {
        "skill_id": "skill_edit_desc_002",
        "edit_type": "description",
        "old_value": "原功能描述",
        "new_value": "完全重构后的功能描述，涵盖了更多使用场景和边界情况处理",
        "expected_version_bump": "minor"
    },

    # ========== 路由配置编辑 ==========
    "update_routing_keywords": {
        "skill_id": "skill_edit_routing_001",
        "edit_type": "routing",
        "old_routing": {
            "trigger_keywords": ["关键词A"],
            "priority": 5
        },
        "new_routing": {
            "trigger_keywords": ["关键词A", "关键词B", "关键词C"],
            "priority": 8
        },
        "expected_version_bump": "minor"
    },

    "update_routing_priority_only": {
        "skill_id": "skill_edit_routing_002",
        "edit_type": "routing",
        "old_routing": {
            "trigger_keywords": ["错误", "bug"],
            "priority": 5
        },
        "new_routing": {
            "trigger_keywords": ["错误", "bug"],
            "priority": 9
        },
        "expected_version_bump": "patch"
    },

    # ========== 工作流程编辑 ==========
    "update_workflow_steps": {
        "skill_id": "skill_edit_workflow_001",
        "edit_type": "workflow",
        "old_steps": ["步骤1: 分析问题", "步骤2: 给出方案"],
        "new_steps": [
            "步骤1: 理解需求",
            "步骤2: 分析问题",
            "步骤3: 制定方案",
            "步骤4: 执行实施",
            "步骤5: 验证结果"
        ],
        "expected_version_bump": "minor"
    },

    "minor_workflow_refinement": {
        "skill_id": "skill_edit_workflow_002",
        "edit_type": "workflow",
        "old_steps": ["收集信息", "给出建议"],
        "new_steps": ["收集信息", "分析情况", "给出建议"],
        "expected_version_bump": "patch"
    },

    # ========== 分类编辑 ==========
    "update_category": {
        "skill_id": "skill_edit_cat_001",
        "edit_type": "category",
        "old_category": "uncategorized",
        "new_category": "programming",
        "expected_version_bump": None  # 分类变更不触发版本变更
    },

    "move_to_different_category": {
        "skill_id": "skill_edit_cat_002",
        "edit_type": "category",
        "old_category": "debugging",
        "new_category": "analysis",
        "expected_version_bump": None
    },

    # ========== 批量编辑 ==========
    "batch_edit_tags": {
        "skill_ids": ["skill_batch_001", "skill_batch_002", "skill_batch_003"],
        "edit_type": "tags",
        "old_tags": ["旧标签"],
        "new_tags": ["新标签", "批量更新"],
        "expected_version_bump": None  # 批量编辑由外部控制版本
    },

    "batch_update_priority": {
        "skill_ids": ["skill_batch_004", "skill_batch_005"],
        "edit_type": "priority",
        "old_priority": 5,
        "new_priority": 8,
        "expected_version_bump": None
    },

    # ========== 标签编辑 ==========
    "add_single_tag": {
        "skill_id": "skill_edit_tag_001",
        "edit_type": "tags",
        "old_tags": ["标签A", "标签B"],
        "new_tags": ["标签A", "标签B", "标签C"],
        "expected_version_bump": "patch"
    },

    "replace_all_tags": {
        "skill_id": "skill_edit_tag_002",
        "edit_type": "tags",
        "old_tags": ["old", "tags"],
        "new_tags": ["new", "tags", "replaced"],
        "expected_version_bump": "minor"
    },

    # ========== 版本格式边界情况 ==========
    "manual_version_bump": {
        "skill_id": "skill_edit_version_001",
        "edit_type": "version",
        "old_version": "1.0.0",
        "new_version": "2.0.0",
        "expected_version_bump": None  # 手动指定版本
    },

    # ========== 规则编辑 ==========
    "update_rules_must_do": {
        "skill_id": "skill_edit_rules_001",
        "edit_type": "rules",
        "old_rules": {
            "rules_must_do": ["必须验证输入"],
            "rules_dont": ["不要跳过检查"]
        },
        "new_rules": {
            "rules_must_do": ["必须验证输入", "必须记录日志"],
            "rules_dont": ["不要跳过检查", "不要泄露敏感信息"]
        },
        "expected_version_bump": "minor"
    },

    "minor_rules_update": {
        "skill_id": "skill_edit_rules_002",
        "edit_type": "rules",
        "old_rules": {
            "rules_must_do": ["验证输入"],
        },
        "new_rules": {
            "rules_must_do": ["验证输入"],  # 无变化
        },
        "expected_version_bump": None  # 无实际变化
    },

    # ========== Markdown 格式测试 ==========
    "markdown_frontmatter_sync": {
        "skill_id": "skill_edit_frontmatter_001",
        "edit_type": "frontmatter",
        "changes": {
            "description": "同步更新的描述",
            "priority": 9
        },
        "expected_version_bump": "patch"
    },

    "markdown_body_content_update": {
        "skill_id": "skill_edit_body_001",
        "edit_type": "body",
        "changes": {
            "new_sections": [
                "## 注意事项\n- 这是新添加的内容"
            ],
            "updated_steps": [
                "步骤1: 更新后的步骤"
            ]
        },
        "expected_version_bump": "patch"
    },
}


def get_edit_test_cases() -> List[EditTestCase]:
    """获取编辑测试用例"""
    cases = []
    for name, data in EDITION_DATASETS.items():
        if "skill_id" in data and "edit_type" in data:
            if data.get("expected_version_bump") is not None:
                cases.append(EditTestCase(
                    skill_id=data["skill_id"],
                    edit_type=data["edit_type"],
                    old_value=data.get("old_value") or data.get("old_routing") or data.get("old_tags"),
                    new_value=data.get("new_value") or data.get("new_routing") or data.get("new_tags"),
                    expected_version_bump=data["expected_version_bump"]
                ))
    return cases


def get_batch_edit_cases() -> List[Dict[str, Any]]:
    """获取批量编辑测试用例"""
    cases = []
    for name, data in EDITION_DATASETS.items():
        if "skill_ids" in data:
            cases.append({
                "skill_ids": data["skill_ids"],
                "edit_type": data["edit_type"],
                "old_value": data.get("old_value") or data.get("old_tags") or data.get("old_priority"),
                "new_value": data.get("new_value") or data.get("new_tags") or data.get("new_priority"),
                "expected_version_bump": data.get("expected_version_bump")
            })
    return cases
