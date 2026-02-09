"""API 端点集成测试

测试 FastAPI 端点的 HTTP 接口响应。
"""
import pytest
from fastapi.testclient import TestClient

from timem_evolve.api.main import app


@pytest.fixture
def client():
    """测试客户端 fixture"""
    return TestClient(app)


class TestHealthEndpoint:
    """健康检查端点测试"""

    def test_health_check(self, client):
        """测试健康检查"""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["version"] == "0.2.0"

    def test_root_redirect(self, client):
        """测试根路径重定向"""
        response = client.get("/")

        assert response.status_code == 200  # 或 307 重定向


class TestSkillsEndpoints:
    """技能端点测试"""

    def test_list_skills_empty(self, client):
        """测试列出技能（空列表）"""
        response = client.get("/skills")

        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_list_skills_with_params(self, client):
        """测试带参数的技能列表"""
        response = client.get("/skills", params={"category": "test", "limit": 10})

        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_search_skills(self, client):
        """测试搜索技能"""
        response = client.get("/skills/search", params={"query": "测试"})

        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_search_skills_with_category(self, client):
        """测试带分类的技能搜索"""
        response = client.get("/skills/search", params={
            "query": "测试",
            "category": "test",
            "top_k": 5
        })

        assert response.status_code == 200

    def test_get_nonexistent_skill(self, client):
        """测试获取不存在的技能"""
        response = client.get("/skills/non_existent_skill")

        assert response.status_code == 404


class TestSkillsExportEndpoint:
    """技能导出端点测试"""

    def test_export_skill_markdown_not_found(self, client):
        """测试导出不存在的技能"""
        response = client.get("/skills/non_existent/export")

        # 如果 RegistryDAO 未启用，返回 501
        # 如果技能不存在，返回 404
        assert response.status_code in [404, 501]

    def test_export_skill_content_type(self, client):
        """测试导出内容的 Content-Type"""
        response = client.get("/skills/test/export")

        if response.status_code == 200:
            assert "text/markdown" in response.headers["content-type"]


class TestSkillsImportEndpoint:
    """技能导入端点测试"""

    def test_import_empty_body(self, client):
        """测试导入空内容"""
        response = client.post("/skills/import", content="")

        # 空内容或未启用 RegistryDAO
        assert response.status_code in [400, 501]

    def test_import_invalid_markdown(self, client):
        """测试导入无效 Markdown"""
        response = client.post(
            "/skills/import",
            content="这不是有效的 Markdown",
            headers={"Content-Type": "text/markdown"}
        )

        assert response.status_code in [400, 501]


class TestSkillsEvolutionEndpoint:
    """技能变更历史端点测试"""

    def test_get_evolution_not_found(self, client):
        """测试获取不存在的变更历史"""
        response = client.get("/skills/non_existent/evolution")

        # 技能不存在返回 404，RegistryDAO 未启用返回 501
        assert response.status_code in [404, 501]

    def test_get_evolution_response_format(self, client):
        """测试变更历史响应格式"""
        response = client.get("/skills/test/evolution")

        if response.status_code == 200:
            data = response.json()
            assert "evolution_log" in data
            assert "skill_id" in data


class TestSkillsVersionEndpoint:
    """技能版本端点测试"""

    def test_version_not_found(self, client):
        """测试版本更新（技能不存在）"""
        response = client.post(
            "/skills/non_existent/version",
            params={"increment_type": "minor"}
        )

        assert response.status_code in [404, 501]

    def test_version_invalid_type(self, client):
        """测试无效的版本类型"""
        response = client.post(
            "/skills/test/version",
            params={"increment_type": "invalid"}
        )

        # 无效类型返回 400，RegistryDAO 未启用返回 501
        assert response.status_code in [400, 501]


class TestSkillsDeleteEndpoint:
    """技能删除端点测试"""

    def test_delete_nonexistent_skill(self, client):
        """测试删除不存在的技能"""
        response = client.delete("/skills/non_existent_skill")

        # 返回 404 或 400/500（删除失败）
        assert response.status_code in [404, 400, 500]


class TestRegistryEndpoints:
    """注册表端点测试"""

    def test_registry_status(self, client):
        """测试注册表状态"""
        response = client.get("/registry/status")

        assert response.status_code == 200
        data = response.json()
        assert "backend" in data
        assert "total_skills" in data
        assert "is_using_registry" in data

    def test_rebuild_index_not_enabled(self, client):
        """测试重建索引（RegistryDAO 未启用）"""
        response = client.post("/registry/index/rebuild")

        # RegistryDAO 未启用返回 501
        assert response.status_code in [200, 501]


class TestRulesEndpoints:
    """规则端点测试"""

    def test_list_rules(self, client):
        """测试列出规则"""
        response = client.get("/rules")

        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_search_rules(self, client):
        """测试搜索规则"""
        response = client.get("/rules/search", params={"query": "测试"})

        assert response.status_code == 200
        assert isinstance(response.json(), list)


class TestSessionsEndpoints:
    """会话端点测试"""

    def test_list_sessions(self, client):
        """测试列出会话"""
        response = client.get("/sessions")

        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_list_sessions_with_params(self, client):
        """测试带参数的会话列表"""
        response = client.get("/sessions", params={"outcome": "success", "limit": 10})

        assert response.status_code == 200

    def test_get_nonexistent_session(self, client):
        """测试获取不存在的会话"""
        response = client.get("/sessions/non_existent_session")

        assert response.status_code == 404


class TestFeedbacksEndpoints:
    """反馈端点测试"""

    def test_list_feedbacks(self, client):
        """测试列出反馈"""
        response = client.get("/feedbacks")

        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_list_feedbacks_with_params(self, client):
        """测试带参数的反馈列表"""
        response = client.get("/feedbacks", params={
            "session_id": "test",
            "learned": True,
            "limit": 10
        })

        assert response.status_code == 200


class TestCoachEndpoints:
    """Coach 端点测试"""

    def test_get_coach_state(self, client):
        """测试获取 Coach 状态"""
        response = client.get("/coach/state")

        assert response.status_code == 200

    def test_list_coach_tasks(self, client):
        """测试列出 Coach 任务"""
        response = client.get("/coach/tasks")

        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_list_coach_tasks_with_status(self, client):
        """测试带状态的 Coach 任务列表"""
        response = client.get("/coach/tasks", params={"status": "pending"})

        assert response.status_code == 200
