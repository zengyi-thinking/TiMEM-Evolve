"""测试反馈数据集：覆盖好评、差评、边界情况"""
from typing import Dict, Any, List
from enum import Enum
from datetime import datetime


class FeedbackType(Enum):
    """反馈类型枚举"""
    POSITIVE_SKILL = "好评 → 技能"
    NEGATIVE_RULE = "差评 → 规则"
    EDGE_CASE = "边界情况"


# 模拟消息类型
class MockMessage:
    def __init__(self, role: str, content: str):
        self.role = role
        self.content = content

    def get(self, key: str, default=None):
        return getattr(self, key, default)


# 模拟会话
class MockSession:
    def __init__(self, session_id: str, messages: List[MockMessage], task: str, outcome: str = "success"):
        self.session_id = session_id
        self.messages = messages
        self.task = task
        self.outcome = outcome
        self.timestamp = datetime.now()

    def model_dump(self):
        return {
            "session_id": self.session_id,
            "task": self.task,
            "messages": [m.model_dump() for m in self.messages],
            "outcome": self.outcome,
            "timestamp": self.timestamp.isoformat()
        }


# 模拟反馈
class MockFeedback:
    def __init__(self, feedback_id: str, session_id: str, message_index: int,
                 rating: str, comment: str = None):
        self.feedback_id = feedback_id
        self.session_id = session_id
        self.message_index = message_index
        self.rating = rating
        self.comment = comment
        self.learned = False
        self.learned_skill_id = None
        self.learned_rule_id = None


FEEDBACK_DATASETS: Dict[str, Dict[str, Any]] = {
    # ========== 好评 → 技能提炼 ==========
    "explain_code_clearly": {
        "type": FeedbackType.POSITIVE_SKILL,
        "session": MockSession(
            session_id="session_explain_001",
            task="解释代码作用",
            messages=[
                MockMessage(role="user", content="请解释这段代码的作用"),
                MockMessage(role="assistant", content="这段代码实现了快速排序算法，它通过分治策略将数组递归地分成两部分进行排序。")
            ],
            outcome="success"
        ),
        "feedback": MockFeedback(
            feedback_id="feedback_001",
            session_id="session_explain_001",
            message_index=1,
            rating="positive",
            comment="解释非常清晰，步骤详细易懂"
        ),
        "expected": {
            "learned": True,
            "outcome_type": "skill",
            "skill_category": "communication",
            "routing_keywords": ["解释", "代码"]
        }
    },

    "debug_python_error": {
        "type": FeedbackType.POSITIVE_SKILL,
        "session": MockSession(
            session_id="session_debug_001",
            task="调试 Python 错误",
            messages=[
                MockMessage(role="user", content="Python 报错: NameError: name 'x' is not defined"),
                MockMessage(role="assistant", content="这个错误是因为变量未定义。请检查：1. 变量名拼写 2. 变量是否在作用域内 3. 是否先赋值后使用")
            ],
            outcome="success"
        ),
        "feedback": MockFeedback(
            feedback_id="feedback_002",
            session_id="session_debug_001",
            message_index=1,
            rating="positive",
            comment="直接定位到问题根源，修复方案有效"
        ),
        "expected": {
            "learned": True,
            "outcome_type": "skill",
            "skill_category": "debugging",
            "routing_keywords": ["报错", "错误", "debug"]
        }
    },

    "write_clean_documentation": {
        "type": FeedbackType.POSITIVE_SKILL,
        "session": MockSession(
            session_id="session_doc_001",
            task="编写 API 文档",
            messages=[
                MockMessage(role="user", content="请为这个函数编写文档"),
                MockMessage(role="assistant", content="```python\ndef calculate_average(numbers):\n    '''计算数值列表的平均值\n\n    Args:\n        numbers: 数值列表\n\n    Returns:\n        float: 平均值，如果列表为空返回 0\n    '''\n    if not numbers:\n        return 0\n    return sum(numbers) / len(numbers)\n```")
            ],
            outcome="success"
        ),
        "feedback": MockFeedback(
            feedback_id="feedback_003",
            session_id="session_doc_001",
            message_index=1,
            rating="positive",
            comment="文档格式规范，参数说明清晰"
        ),
        "expected": {
            "learned": True,
            "outcome_type": "skill",
            "skill_category": "writing",
            "routing_keywords": ["文档", "注释", "编写"]
        }
    },

    # ========== 差评 → 规则提炼 ==========
    "diagnosis_incomplete": {
        "type": FeedbackType.NEGATIVE_RULE,
        "session": MockSession(
            session_id="session_diag_001",
            task="解决程序崩溃",
            messages=[
                MockMessage(role="user", content="我的程序崩溃了"),
                MockMessage(role="assistant", content="可能是内存问题，请增加内存")
            ],
            outcome="failure"
        ),
        "feedback": MockFeedback(
            feedback_id="feedback_004",
            session_id="session_diag_001",
            message_index=1,
            rating="negative",
            comment="诊断不全面，没有要求提供错误信息就下结论"
        ),
        "expected": {
            "learned": True,
            "outcome_type": "rule",
            "rule_constraint": "诊断前必须收集完整错误信息"
        }
    },

    "terminology_too_complex": {
        "type": FeedbackType.NEGATIVE_RULE,
        "session": MockSession(
            session_id="session_term_001",
            task="解释闭包概念",
            messages=[
                MockMessage(role="user", content="什么是闭包？"),
                MockMessage(role="assistant", content="闭包是词法作用域和一级函数的组合。当内部函数引用了外部函数的变量时，就形成了一个闭包，允许内部函数访问外部函数的作用域。")
            ],
            outcome="failure"
        ),
        "feedback": MockFeedback(
            feedback_id="feedback_005",
            session_id="session_term_001",
            message_index=1,
            rating="negative",
            comment="术语太专业，听不懂"
        ),
        "expected": {
            "learned": True,
            "outcome_type": "rule",
            "rule_must_do": "使用通俗语言解释专业术语"
        }
    },

    "code_without_explanation": {
        "type": FeedbackType.NEGATIVE_RULE,
        "session": MockSession(
            session_id="session_code_001",
            task="解决编程问题",
            messages=[
                MockMessage(role="user", content="如何实现列表去重？"),
                MockMessage(role="assistant", content="```python\nlist(set(original_list))\n```")
            ],
            outcome="failure"
        ),
        "feedback": MockFeedback(
            feedback_id="feedback_006",
            session_id="session_code_001",
            message_index=1,
            rating="negative",
            comment="只给了代码，没有解释原理"
        ),
        "expected": {
            "learned": True,
            "outcome_type": "rule",
            "rule_must_do": "提供代码时必须附带说明"
        }
    },

    # ========== 边界情况 ==========
    "empty_comment_positive": {
        "type": FeedbackType.EDGE_CASE,
        "session": MockSession(
            session_id="session_empty_001",
            task="简单问候",
            messages=[
                MockMessage(role="user", content="你好"),
                MockMessage(role="assistant", content="你好！有什么可以帮你的？")
            ],
            outcome="success"
        ),
        "feedback": MockFeedback(
            feedback_id="feedback_007",
            session_id="session_empty_001",
            message_index=1,
            rating="positive",
            comment=""  # 空评论
        ),
        "expected": {
            "learned": False,
            "outcome_type": None
        }
    },

    "neutral_feedback": {
        "type": FeedbackType.EDGE_CASE,
        "session": MockSession(
            session_id="session_neutral_001",
            task="简单对话",
            messages=[
                MockMessage(role="user", content="谢谢"),
                MockMessage(role="assistant", content="不客气")
            ],
            outcome="success"
        ),
        "feedback": MockFeedback(
            feedback_id="feedback_008",
            session_id="session_neutral_001",
            message_index=1,
            rating="neutral",  # 中性反馈（不是 positive/negative）
            comment="还行吧"
        ),
        "expected": {
            "learned": False,
            "outcome_type": None
        }
    },

    "short_positive_feedback": {
        "type": FeedbackType.EDGE_CASE,
        "session": MockSession(
            session_id="session_short_001",
            task="技术咨询",
            messages=[
                MockMessage(role="user", content="如何安装 Python 包？"),
                MockMessage(role="assistant", content="使用 pip install 命令，例如：pip install requests")
            ],
            outcome="success"
        ),
        "feedback": MockFeedback(
            feedback_id="feedback_009",
            session_id="session_short_001",
            message_index=1,
            rating="positive",
            comment="好"  # 简短反馈
        ),
        "expected": {
            "learned": True,  # 仍是好评，应该学习
            "outcome_type": "skill"
        }
    },
}
