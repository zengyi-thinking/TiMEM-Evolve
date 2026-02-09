"""技能复用测试数据集：测试跨会话匹配和复用"""
from typing import Dict, Any, List
from dataclasses import dataclass


@dataclass
class SkillRoutingTestCase:
    """技能路由匹配测试用例"""
    skill_name: str
    category: str
    trigger_keywords: List[str]
    priority: int
    test_inputs: List[Dict[str, Any]]


@dataclass
class SkillCompositionCase:
    """技能组合测试用例"""
    base_skills: List[Dict[str, Any]]
    composed_skill: Dict[str, Any]
    test_input: str
    expected_skills: List[str]


REUSAGE_DATASETS: Dict[str, Dict[str, Any]] = {
    # ========== 关键词匹配测试 ==========
    "code_explanation_routing": {
        "skill": {
            "name": "代码解释技能",
            "category": "communication",
            "routing": {
                "trigger_keywords": ["解释", "代码", "作用", "说明"],
                "priority": 8
            }
        },
        "test_cases": [
            {"input": "请解释这个函数的逻辑", "expected_match": True, "reason": "包含'解释'关键词"},
            {"input": "这段代码是做什么的？", "expected_match": True, "reason": "包含'代码'关键词"},
            {"input": "帮我看看这个算法", "expected_match": True, "reason": "代码相关请求"},
            {"input": "写一个排序算法", "expected_match": False, "reason": "这是创建，不是解释"},
            {"input": "如何运行这个程序？", "expected_match": False, "reason": "运行相关，不是解释"},
        ]
    },

    "python_debug_routing": {
        "skill": {
            "name": "Python 调试技能",
            "category": "debugging",
            "routing": {
                "trigger_keywords": ["报错", "错误", "bug", "调试", "exception", "python"],
                "priority": 9
            }
        },
        "test_cases": [
            {"input": "Python 报错 IndexError", "expected_match": True, "reason": "包含'报错'和'Python'"},
            {"input": "我的代码有个 bug", "expected_match": True, "reason": "包含'bug'"},
            {"input": "调试一下这个脚本", "expected_match": True, "reason": "包含'调试'"},
            {"input": "出现 ValueError 异常", "expected_match": True, "reason": "包含'异常'和错误类型"},
            {"input": "写一个 Python 脚本", "expected_match": False, "reason": "这是创建任务"},
            {"input": "Python 是什么？", "expected_match": False, "reason": "这是概念问题，不是调试"},
        ]
    },

    "documentation_routing": {
        "skill": {
            "name": "文档编写技能",
            "category": "writing",
            "routing": {
                "trigger_keywords": ["文档", "注释", "说明", "README", "编写"],
                "priority": 7
            }
        },
        "test_cases": [
            {"input": "请为这个函数写注释", "expected_match": True, "reason": "包含'注释'"},
            {"input": "如何编写 README？", "expected_match": True, "reason": "包含'编写'和'README'"},
            {"input": "项目文档模板", "expected_match": True, "reason": "包含'文档'"},
            {"input": "写一篇文章", "expected_match": True, "reason": "包含'写'和'文章'"},
            {"input": "代码规范有哪些？", "expected_match": False, "reason": "这是问答，不是编写"},
        ]
    },

    "analysis_routing": {
        "skill": {
            "name": "代码分析技能",
            "category": "analysis",
            "routing": {
                "trigger_keywords": ["分析", "检查", "审核", "评估", "review"],
                "priority": 8
            }
        },
        "test_cases": [
            {"input": "请分析这段代码的性能", "expected_match": True, "reason": "包含'分析'"},
            {"input": "帮我检查是否有内存泄漏", "expected_match": True, "reason": "包含'检查'"},
            {"input": "代码审核建议", "expected_match": True, "reason": "包含'审核'"},
            {"input": "评估这个方案是否可行", "expected_match": True, "reason": "包含'评估'"},
            {"input": "这段代码有问题吗？", "expected_match": True, "reason": "分析相关"},
        ]
    },

    # ========== 优先级排序测试 ==========
    "priority_ordering": {
        "skills": [
            {
                "name": "高频调试",
                "routing": {"trigger_keywords": ["错误", "bug", "报错"], "priority": 10}
            },
            {
                "name": "中频解释",
                "routing": {"trigger_keywords": ["解释", "说明"], "priority": 7}
            },
            {
                "name": "低频文档",
                "routing": {"trigger_keywords": ["文档", "注释"], "priority": 4}
            }
        ],
        "test_input": "代码报错了怎么解决？",
        "expected_top_match": "高频调试",
        "expected_ordering": ["高频调试", "中频解释"]
    },

    # ========== 技能组合测试 ==========
    "skill_composition_basic": {
        "base_skills": [
            {"name": "代码解释", "category": "communication", "routing": {"trigger_keywords": ["解释"], "priority": 7}},
            {"name": "错误诊断", "category": "debugging", "routing": {"trigger_keywords": ["诊断"], "priority": 8}}
        ],
        "composed_skill": {
            "name": "诊断并解释代码错误",
            "derived_from": ["代码解释", "错误诊断"]
        },
        "test_input": "请诊断并解释这个 Python 报错",
        "expected_skills": ["错误诊断", "代码解释"]
    },

    "skill_composition_complex": {
        "base_skills": [
            {"name": "需求分析", "category": "analysis", "routing": {"trigger_keywords": ["需求"], "priority": 6}},
            {"name": "代码生成", "category": "programming", "routing": {"trigger_keywords": ["生成", "写"], "priority": 5}},
            {"name": "测试编写", "category": "testing", "routing": {"trigger_keywords": ["测试"], "priority": 7}}
        ],
        "composed_skill": {
            "name": "完整功能开发流程",
            "derived_from": ["需求分析", "代码生成", "测试编写"]
        },
        "test_input": "我需要实现一个用户登录功能，包括前端页面、后端接口和测试用例",
        "expected_skills": ["需求分析", "代码生成", "测试编写"]
    },

    # ========== 跨会话复用测试 ==========
    "cross_session_reuse": {
        "session1": {
            "task": "Python NameError 调试",
            "messages": [
                {"role": "user", "content": "Python 报错 NameError: name 'x' is not defined"},
                {"role": "assistant", "content": "这是变量未定义的错误..."}
            ],
            "feedback_rating": "positive",
            "expected_skill": "Python 调试技能"
        },
        "session2": {
            "task": "Python IndexError 调试",
            "messages": [
                {"role": "user", "content": "Python 报错 list index out of range"},
                {"role": "assistant", "content": "这是索引越界错误..."}
            ],
            "expected_reuse": True
        },
        "session3": {
            "task": "Java NullPointerException",
            "messages": [
                {"role": "user", "content": "Java 报错 NullPointerException"},
                {"role": "assistant", "content": "这是空指针错误..."}
            ],
            "expected_reuse": True  # 调试技能可以复用
        }
    },

    # ========== 关键词冲突处理 ==========
    "keyword_conflict_resolution": {
        "skills": [
            {
                "name": "A. Python 调试",
                "category": "debugging",
                "routing": {"trigger_keywords": ["python"], "priority": 8}
            },
            {
                "name": "B. Python 教程",
                "category": "education",
                "routing": {"trigger_keywords": ["python", "学习"], "priority": 6}
            }
        ],
        "test_inputs": [
            {"input": "python 报错了", "expected_skill": "A. Python 调试", "reason": "优先级更高且匹配错误场景"},
            {"input": "我想学习 python", "expected_skill": "B. Python 教程", "reason": "包含'学习'关键词"},
            {"input": "python 基础语法", "expected_skill": "B. Python 教程", "reason": "学习相关"},
        ]
    },

    # ========== 空关键词边界情况 ==========
    "empty_keyword_handling": {
        "skill": {
            "name": "默认技能",
            "routing": {"trigger_keywords": [], "priority": 1}
        },
        "test_cases": [
            {"input": "随机请求", "expected_match": False, "reason": "无关键词不应匹配"},
            {"input": "", "expected_match": False, "reason": "空输入不应匹配"},
        ]
    },
}


def get_routing_test_cases() -> List[SkillRoutingTestCase]:
    """获取路由匹配测试用例"""
    cases = []
    for name, data in REUSAGE_DATASETS.items():
        if "test_cases" in data and "skill" in data:
            skill = data["skill"]
            cases.append(SkillRoutingTestCase(
                skill_name=skill["name"],
                category=skill["category"],
                trigger_keywords=skill["routing"]["trigger_keywords"],
                priority=skill["routing"]["priority"],
                test_inputs=data["test_cases"]
            ))
    return cases


def get_composition_cases() -> List[SkillCompositionCase]:
    """获取技能组合测试用例"""
    cases = []
    for name, data in REUSAGE_DATASETS.items():
        if "base_skills" in data and "composed_skill" in data:
            cases.append(SkillCompositionCase(
                base_skills=data["base_skills"],
                composed_skill=data["composed_skill"],
                test_input=data.get("test_input", ""),
                expected_skills=data["expected_skills"]
            ))
    return cases
