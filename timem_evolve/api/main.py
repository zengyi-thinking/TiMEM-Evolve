"""FastAPI 主应用 v2.0

支持 M.S.F.S 和 E.S.P 格式的技能管理
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse

from ..dao import UnifiedDAO
from ..models import (
    Feedback,
    FeedbackCreate,
    Rule,
    Session,
    SessionCreate,
    Skill,
    CoachTask,
    CoachTaskCreate,
    CoachState,
)
from ..services.analyzer_service import AnalyzerService
from ..services.coach_service import CoachService as CoachServiceImpl
from ..services.learner_service import LearnerService
from ..services.session_service import SessionService


# ==================== 全局实例 ====================

# 使用 UnifiedDAO（自动路由到 RegistryDAO 或 MemoryDAO）
dao = UnifiedDAO(data_dir="./data")
session_service = SessionService(dao)
learner_service = LearnerService(dao)
analyzer_service = AnalyzerService()
coach_service = CoachServiceImpl(dao, learner_service)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 初始化数据库
    await dao.init_db()
    yield
    # 清理资源（如果需要）


app = FastAPI(
    title="TiMEM-Evolve API",
    version="0.2.0",
    description="自进化智能体框架的后端服务 - 支持 M.S.F.S 和 E.S.P",
    lifespan=lifespan
)


@app.get("/")
async def root():
    """根路径，重定向到 API 文档"""
    return RedirectResponse(url="/docs")


@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "version": "0.2.0",
        "backend": dao.get_backend_info()
    }


# ==================== Sessions ====================

@app.post("/sessions", response_model=Session)
async def add_session(session_create: SessionCreate):
    """添加新会话"""
    return await session_service.add_session(session_create)


@app.get("/sessions/{session_id}", response_model=Optional[Session])
async def get_session(session_id: str):
    """获取会话详情"""
    return await session_service.get_session(session_id)


@app.get("/sessions", response_model=List[Session])
async def list_sessions(
    outcome: Optional[str] = None,
    limit: int = 100
):
    """列出会话"""
    return await session_service.list_sessions(outcome=outcome, limit=limit)


# ==================== Feedbacks ====================

@app.post("/feedbacks", response_model=Feedback)
async def add_feedback(feedback_create: FeedbackCreate):
    """添加反馈并触发学习"""
    feedback = Feedback(**feedback_create.model_dump())

    # 1. 保存反馈
    dao.save_feedback(feedback)

    # 2. 触发学习
    learned_id = await learner_service.learn_from_feedback(feedback)

    # 3. 重新获取反馈（可能已更新 learned 状态）
    if learned_id:
        feedback = dao.get_feedback(feedback.feedback_id)

    return feedback


@app.get("/feedbacks", response_model=List[Feedback])
async def list_feedbacks(
    session_id: Optional[str] = None,
    learned: Optional[bool] = None,
    limit: int = 100
):
    """列出反馈"""
    return dao.list_feedbacks(
        session_id=session_id,
        learned=learned,
        limit=limit
    )


# ==================== Skills (v2.0 - 支持 M.S.F.S) ====================

@app.get("/skills", response_model=List[Skill])
async def list_skills(
    category: Optional[str] = None,
    limit: int = 100
):
    """列出技能

    Args:
        category: 可选分类过滤（仅 RegistryDAO 支持）
        limit: 最大返回数量
    """
    return await dao.list_skills(category=category, limit=limit)


@app.get("/skills/search", response_model=List[Skill])
async def search_skills(
    query: str,
    category: Optional[str] = None,
    top_k: int = 5
):
    """搜索技能（多维度匹配）

    Args:
        query: 搜索查询
        category: 可选分类过滤
        top_k: 返回前 K 个结果
    """
    return await dao.search_skills(query=query, category=category, top_k=top_k)


@app.post("/skills/{skill_id}/evolve")
async def evolve_skill(skill_id: str, updates: Dict[str, Any]):
    """技能进化接口（预留）

    Args:
        skill_id: 技能 ID
        updates: 更新内容（包含 change_summary）

    Request Body:
        {
            "updates": { "name": "新名称", ... },
            "change_summary": "优化了工作流程"
        }
    """
    change_summary = updates.pop("change_summary", "手动更新")

    skill = await dao.update_skill(
        skill_id=skill_id,
        updates=updates,
        change_summary=change_summary
    )

    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")

    return skill


@app.delete("/skills/{skill_id}")
async def delete_skill(skill_id: str):
    """删除技能

    Args:
        skill_id: 技能 ID

    Returns:
        删除结果
    """
    success = await dao.delete_skill(skill_id)

    if not success:
        raise HTTPException(status_code=404, detail="Skill not found or delete failed")

    return {"success": True, "skill_id": skill_id}


# ==================== Rules ====================

@app.get("/rules", response_model=List[Rule])
async def list_rules(limit: int = 100):
    """列出规则"""
    return dao.list_rules(limit=limit)


@app.get("/rules/search", response_model=List[Rule])
async def search_rules(query: str, top_k: int = 5):
    """搜索规则"""
    return dao.search_rules(query=query, top_k=top_k)


# ==================== Learning ====================

@app.post("/learn/session/{session_id}", response_model=Optional[str])
async def learn_from_session(session_id: str):
    """从完整的会话中学习（成功->技能，失败->规则）"""
    session = await session_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.outcome == "success":
        skill = await learner_service.extract_skill_from_session(session)
        return skill.skill_id if skill else None
    elif session.outcome == "failure":
        rule = await learner_service.extract_rule_from_session(session)
        return rule.rule_id if rule else None

    return None


# ==================== Coach ====================

@app.get("/coach/state", response_model=CoachState)
async def get_coach_state():
    """获取 Coach 模块的统计状态"""
    return coach_service.get_state()


@app.post("/coach/generate_task", response_model=CoachTask)
async def generate_coach_task(task_create: CoachTaskCreate):
    """生成一个新的 Coach 任务"""
    try:
        task = await coach_service.generate_task(task_create.business_goal)
        return task
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/coach/run_task/{task_id}", response_model=CoachTask)
async def run_coach_task(task_id: str):
    """运行一个 Coach 任务"""
    try:
        tasks = coach_service.list_tasks()
        task = next((t for t in tasks if t.task_id == task_id), None)

        if not task:
            raise HTTPException(status_code=404, detail="Coach Task not found")

        if task.status != "pending":
            raise HTTPException(
                status_code=400,
                detail=f"Task status is {task.status}, only 'pending' tasks can be run."
            )

        # 异步运行任务
        updated_task = await coach_service.run_task(task)
        return updated_task

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/coach/tasks", response_model=List[CoachTask])
async def list_coach_tasks(status: Optional[str] = None):
    """列出 Coach 任务"""
    return coach_service.list_tasks(status=status)


# ==================== Registry Extension (v2.0 新增) ====================

@app.get("/skills/{skill_id}/export")
async def export_skill_markdown(skill_id: str):
    """导出技能为 E.S.P Markdown 格式

    Args:
        skill_id: 技能 ID

    Returns:
        Markdown 字符串（纯文本响应）
    """
    if not dao.is_using_registry():
        raise HTTPException(
            status_code=501,
            detail="此功能仅在使用 RegistryDAO (M.S.F.S) 时可用"
        )

    markdown = await dao.export_skill_markdown(skill_id)

    if not markdown:
        raise HTTPException(status_code=404, detail="Skill not found")

    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(
        content=markdown,
        media_type="text/markdown; charset=utf-8"
    )


@app.post("/skills/import")
async def import_skill_from_markdown(
    request: Request,
    skill_id: Optional[str] = None
):
    """从 E.S.P Markdown 导入技能

    Args:
        request: FastAPI Request 对象
        skill_id: 可选的新技能 ID（通过 Query 参数传递）

    Request Body:
        raw markdown content (string)

    Query Parameters:
        skill_id: 可选的技能 ID

    Returns:
        导入的 Skill 对象
    """
    if not dao.is_using_registry():
        raise HTTPException(
            status_code=501,
            detail="此功能仅在使用 RegistryDAO (M.S.F.S) 时可用"
        )

    # 读取原始请求体
    markdown_content = await request.body()

    # 尝试解码
    try:
        markdown_content = markdown_content.decode("utf-8")
    except (UnicodeDecodeError, AttributeError):
        raise HTTPException(
            status_code=400,
            detail="请求体必须是有效的 UTF-8 文本"
        )

    if not markdown_content or not markdown_content.strip():
        raise HTTPException(
            status_code=400,
            detail="请求体不能为空"
        )

    skill = await dao.import_skill_from_markdown(
        markdown_content=markdown_content,
        skill_id=skill_id
    )

    if not skill:
        raise HTTPException(
            status_code=400,
            detail="导入失败：Markdown 格式不正确或解析失败"
        )

    return skill


@app.get("/skills/{skill_id}/evolution")
async def get_skill_evolution(skill_id: str):
    """获取技能的变更历史

    Args:
        skill_id: 技能 ID

    Returns:
        变更历史记录列表，每项包含 timestamp, version, summary, source
    """
    if not dao.is_using_registry():
        raise HTTPException(
            status_code=501,
            detail="此功能仅在使用 RegistryDAO (M.S.F.S) 时可用"
        )

    evolution_log = await dao.get_evolution_log(skill_id)

    # 检查技能是否存在
    skill = await dao.get_skill(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")

    return {
        "skill_id": skill_id,
        "skill_name": skill.name,
        "evolution_log": evolution_log,
        "total_entries": len(evolution_log)
    }


@app.post("/registry/index/rebuild")
async def rebuild_registry_index():
    """重建技能索引

    扫描 skills/ 目录，重新构建 _index.json

    Returns:
        重建结果摘要，包含 total_skills, successful, failed, failed_skills
    """
    if not dao.is_using_registry():
        raise HTTPException(
            status_code=501,
            detail="此功能仅在使用 RegistryDAO (M.S.F.S) 时可用"
        )

    result = await dao.rebuild_index()
    return result


@app.post("/skills/{skill_id}/version")
async def increment_skill_version(
    skill_id: str,
    increment_type: str = "patch",
    change_summary: Optional[str] = None
):
    """创建技能的新版本

    Args:
        skill_id: 技能 ID
        increment_type: 版本自增类型 ("major", "minor", "patch")
        change_summary: 变更摘要（可选）

    Query Parameters:
        increment_type: 版本自增类型，默认 "patch"
        change_summary: 变更摘要，可选

    Returns:
        更新后的 Skill 对象
    """
    if not dao.is_using_registry():
        raise HTTPException(
            status_code=501,
            detail="此功能仅在使用 RegistryDAO (M.S.F.S) 时可用"
        )

    # 验证 increment_type
    if increment_type not in ["major", "minor", "patch"]:
        raise HTTPException(
            status_code=400,
            detail="increment_type 必须是 'major', 'minor' 或 'patch'"
        )

    skill = await dao.increment_skill_version(
        skill_id=skill_id,
        increment_type=increment_type,
        change_summary=change_summary
    )

    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")

    return {
        "skill_id": skill.skill_id,
        "name": skill.name,
        "old_version": skill.metadata.get("version", "1.0.0"),
        "new_version": skill.metadata.get("version", "1.0.0"),
        "increment_type": increment_type,
        "change_summary": change_summary,
        "updated_at": skill.updated_at.isoformat()
    }


# ==================== Registry Migration (v2.0 新增) ====================

@app.post("/registry/migrate")
async def trigger_migration():
    """触发 v1.0 -> v2.0 数据迁移

    执行从 skills.json 到 M.S.F.S 的迁移。

    Returns:
        迁移结果摘要
    """
    try:
        # 动态导入迁移脚本
        import sys
        from pathlib import Path

        # 添加 scripts 目录到路径
        scripts_dir = Path(__file__).parent.parent.parent / "scripts"
        sys.path.insert(0, str(scripts_dir))

        from migrate_v1_to_v2 import V1ToV2Migrator

        # 执行迁移
        migrator = V1ToV2Migrator(data_dir="./data", dry_run=False, force=False)
        summary = await migrator.run()

        return {
            "success": True,
            "summary": summary,
            "message": "迁移完成，请查看日志了解详情"
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"迁移失败: {str(e)}"
        )


@app.get("/registry/status")
async def get_registry_status():
    """获取注册表状态

    Returns:
        包含后端配置和统计信息的字典
    """
    backend_info = dao.get_backend_info()

    # 获取技能统计
    skills = await dao.list_skills(limit=1000)

    # 按分类统计
    category_stats: Dict[str, int] = {}
    for skill in skills:
        cat = skill.category if hasattr(skill, 'category') else "unknown"
        category_stats[cat] = category_stats.get(cat, 0) + 1

    return {
        "backend": backend_info,
        "total_skills": len(skills),
        "category_stats": category_stats,
        "is_using_registry": dao.is_using_registry(),
    }


# ==================== 主程序入口 ====================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
