"""数据访问层 (DAO)

提供统一的数据访问接口，支持多种存储后端。

使用方式:
    # 推荐使用 UnifiedDAO（自动路由）
    from timem_evolve.dao import UnifiedDAO

    dao = UnifiedDAO()

    # 技能操作（根据配置路由到 RegistryDAO 或 MemoryDAO）
    await dao.save_skill(skill)
    skill = await dao.get_skill(skill_id)

    # 会话/反馈操作（始终使用 MemoryDAO）
    await dao.save_session(session)
    dao.save_feedback(feedback)

环境变量:
    USE_SKILL_REGISTRY: 是否使用 M.S.F.S 技能注册表 (默认: true)
"""
from .memory_dao import MemoryDAO
from .registry_dao import RegistryDAO
from .unified_dao import UnifiedDAO

__all__ = [
    "MemoryDAO",
    "RegistryDAO",
    "UnifiedDAO",
]
