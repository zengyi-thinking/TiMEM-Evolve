"""技能进化测试数据集：测试版本迭代、变更追踪"""
from typing import Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class EvolutionTestCase:
    """进化测试用例数据类"""
    skill_id: str
    initial_version: str
    evolution_type: str  # "patch", "minor", "major"
    changes: Dict[str, Any]
    expected_version: str
    expected_log_entry: bool = True


@dataclass
class MultiStepEvolutionCase:
    """多步进化测试用例"""
    skill_id: str
    evolution_sequence: List[tuple]  # (type, from_version, to_version, summary)
    expected_final_version: str
    expected_log_entries: int


EVOLUTION_DATASETS: Dict[str, Dict[str, Any]] = {
    # ========== 单步版本进化 ==========
    "patch_evolution": {
        "skill_id": "skill_test_patch_001",
        "initial_version": "1.0.0",
        "evolution_type": "patch",
        "changes": {
            "description": "优化了描述措辞",
            "reason": "用户反馈描述不够清晰"
        },
        "expected_version": "1.0.1",
        "expected_log_entry": True
    },

    "minor_evolution_new_scenario": {
        "skill_id": "skill_test_minor_001",
        "initial_version": "1.0.0",
        "evolution_type": "minor",
        "changes": {
            "applicable_scenarios": ["场景A", "场景B", "新场景C"],
            "trigger_keywords": ["关键词1", "关键词2"],
            "reason": "发现了新的适用场景"
        },
        "expected_version": "1.1.0",
        "expected_log_entry": True
    },

    "major_evolution_workflow": {
        "skill_id": "skill_test_major_001",
        "initial_version": "1.0.0",
        "evolution_type": "major",
        "changes": {
            "workflow_steps": ["新步骤1", "新步骤2", "新步骤3"],
            "reason": "工作流程完全重构"
        },
        "expected_version": "2.0.0",
        "expected_log_entry": True
    },

    "version_rollback_attempt": {
        "skill_id": "skill_test_rollback_001",
        "initial_version": "2.1.0",
        "evolution_type": "patch",
        "changes": {
            "description": "回滚测试",
            "reason": "测试版本回滚场景"
        },
        "expected_version": "2.1.1",  # 仍然是递增
        "expected_log_entry": True
    },

    "minor_evolution_priority": {
        "skill_id": "skill_test_priority_001",
        "initial_version": "1.5.0",
        "evolution_type": "minor",
        "changes": {
            "routing_priority": 8,
            "reason": "提升路由优先级"
        },
        "expected_version": "1.6.0",
        "expected_log_entry": True
    },

    # ========== 多步进化序列 ==========
    "multi_step_evolution": {
        "skill_id": "skill_test_multi_001",
        "evolution_sequence": [
            ("patch", "1.0.0", "1.0.1", "首次优化描述"),
            ("patch", "1.0.1", "1.0.2", "修正措辞"),
            ("minor", "1.0.2", "1.1.0", "新增适用场景"),
            ("major", "1.1.0", "2.0.0", "重构工作流程"),
        ],
        "expected_final_version": "2.0.0",
        "expected_log_entries": 4
    },

    "rapid_patches": {
        "skill_id": "skill_test_rapid_001",
        "evolution_sequence": [
            ("patch", "1.0.0", "1.0.1", "修复拼写错误"),
            ("patch", "1.0.1", "1.0.2", "调整格式"),
            ("patch", "1.0.2", "1.0.3", "更新示例"),
        ],
        "expected_final_version": "1.0.3",
        "expected_log_entries": 3
    },

    "major_then_patches": {
        "skill_id": "skill_test_major_patch_001",
        "evolution_sequence": [
            ("major", "1.0.0", "2.0.0", "大版本重构"),
            ("patch", "2.0.0", "2.0.1", "修复重构后的 bug"),
            ("patch", "2.0.1", "2.0.2", "补充文档"),
        ],
        "expected_final_version": "2.0.2",
        "expected_log_entries": 3
    },

    # ========== 版本格式边界情况 ==========
    "version_with_v_prefix": {
        "skill_id": "skill_test_vprefix_001",
        "initial_version": "v1.0.0",  # 带 v 前缀
        "evolution_type": "patch",
        "changes": {
            "description": "测试版本格式",
            "reason": "测试带前缀版本"
        },
        "expected_version": "1.0.1",  # 应该规范化
        "expected_log_entry": True
    },

    "single_digit_version": {
        "skill_id": "skill_test_single_001",
        "initial_version": "1",  # 单数字版本
        "evolution_type": "minor",
        "changes": {
            "description": "测试单数字版本",
            "reason": "测试版本格式容错"
        },
        "expected_version": "1.1.0",  # 应该规范化为 x.y.z
        "expected_log_entry": True
    },

    "invalid_version": {
        "skill_id": "skill_test_invalid_001",
        "initial_version": "invalid",  # 无效版本
        "evolution_type": "patch",
        "changes": {
            "description": "测试无效版本",
            "reason": "测试版本容错"
        },
        "expected_version": "1.0.1",  # 应该回退到默认值
        "expected_log_entry": True
    },
}


def get_evolution_test_cases() -> List[EvolutionTestCase]:
    """获取单步进化测试用例列表"""
    cases = []
    for name, data in EVOLUTION_DATASETS.items():
        if "evolution_sequence" not in data:
            cases.append(EvolutionTestCase(
                skill_id=data["skill_id"],
                initial_version=data["initial_version"],
                evolution_type=data["evolution_type"],
                changes=data["changes"],
                expected_version=data["expected_version"],
                expected_log_entry=data.get("expected_log_entry", True)
            ))
    return cases


def get_multi_step_cases() -> List[MultiStepEvolutionCase]:
    """获取多步进化测试用例列表"""
    cases = []
    for name, data in EVOLUTION_DATASETS.items():
        if "evolution_sequence" in data:
            cases.append(MultiStepEvolutionCase(
                skill_id=data["skill_id"],
                evolution_sequence=data["evolution_sequence"],
                expected_final_version=data["expected_final_version"],
                expected_log_entries=data["expected_log_entries"]
            ))
    return cases
