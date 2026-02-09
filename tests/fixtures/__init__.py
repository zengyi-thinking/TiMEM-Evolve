"""测试数据集包

提供核心功能测试所需的数据集:
- feedbacks.py: 反馈数据集（好评、差评、边界情况）
- evolutions.py: 技能进化数据集（版本迭代）
- reusage.py: 技能复用数据集（关键词匹配）
- editions.py: 技能编辑数据集（Markdown 编辑）
"""
from .feedbacks import FEEDBACK_DATASETS, FeedbackType
from .evolutions import EVOLUTION_DATASETS
from .reusage import REUSAGE_DATASETS
from .editions import EDITION_DATASETS

__all__ = [
    "FEEDBACK_DATASETS",
    "EVOLUTION_DATASETS",
    "REUSAGE_DATASETS",
    "EDITION_DATASETS",
    "FeedbackType",
]
