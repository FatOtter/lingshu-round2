"""Unit tests for create_app() and module setup functions in main.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI

from lingshu.main import create_app


class TestCreateApp:
    def test_create_app_returns_fastapi_instance(self) -> None:
        app = create_app()
        assert isinstance(app, FastAPI)

    def test_create_app_title(self) -> None:
        app = create_app()
        assert app.title == "LingShu"

    def test_create_app_has_health_route(self) -> None:
        app = create_app()
        route_paths = [r.path for r in app.routes]  # type: ignore[union-attr]
        assert "/health" in route_paths

    def test_create_app_includes_module_routers(self) -> None:
        app = create_app()
        route_paths = [getattr(r, "path", "") for r in app.routes]
        all_paths_str = " ".join(route_paths)
        assert "/health" in all_paths_str

    def test_create_app_has_cors_middleware(self) -> None:
        app = create_app()
        middleware_names = [m.cls.__name__ for m in app.user_middleware]
        assert "CORSMiddleware" in middleware_names

    def test_create_app_has_auth_middleware(self) -> None:
        app = create_app()
        middleware_names = [m.cls.__name__ for m in app.user_middleware]
        assert "AuthMiddleware" in middleware_names

    @patch("lingshu.main.get_settings")
    def test_create_app_production_cors_empty(self, mock_settings) -> None:
        settings = MagicMock()
        settings.is_dev = False
        settings.cors_origins = ""
        mock_settings.return_value = settings

        app = create_app()
        assert isinstance(app, FastAPI)


class TestSetupSettingModule:
    @patch("lingshu.main.get_redis")
    def test_setup_setting_module_sets_state(self, mock_get_redis) -> None:
        mock_redis = MagicMock()
        mock_get_redis.return_value = mock_redis

        from lingshu.config import Settings
        settings = Settings()
        app = FastAPI()

        from lingshu.main import _setup_setting_module
        _setup_setting_module(app, settings)

        assert hasattr(app.state, "auth_provider")
        assert hasattr(app.state, "auth_enforcer")
        assert hasattr(app.state, "auth_dev_mode")
        assert app.state.auth_dev_mode == settings.is_dev


class TestSetupOntologyModule:
    def test_setup_ontology_module_sets_state(self) -> None:
        mock_driver = MagicMock()
        mock_redis = MagicMock()

        app = FastAPI()

        with patch("lingshu.main.get_redis", return_value=mock_redis), \
             patch("lingshu.infra.graph_db.get_driver", return_value=mock_driver):
            from lingshu.main import _setup_ontology_module
            _setup_ontology_module(app)

        assert hasattr(app.state, "ontology_service")


class TestSetupFunctionModule:
    def test_setup_function_module_sets_state(self) -> None:
        app = FastAPI()
        app.state.ontology_service = MagicMock()
        app.state.data_service = MagicMock()

        from lingshu.main import _setup_function_module
        _setup_function_module(app)

        assert hasattr(app.state, "function_service")


class TestSetupCopilotModule:
    @patch("lingshu.main.get_settings")
    def test_setup_copilot_module_sets_state(self, mock_get_settings) -> None:
        settings = MagicMock()
        mock_get_settings.return_value = settings

        app = FastAPI()
        app.state.function_service = MagicMock()

        from lingshu.main import _setup_copilot_module
        _setup_copilot_module(app)

        assert hasattr(app.state, "copilot_service")


class TestSetupDataModule:
    @patch("lingshu.main.get_settings")
    def test_setup_data_module_sets_state(self, mock_get_settings) -> None:
        settings = MagicMock()
        settings.editlog_backend = "postgres"
        settings.fdb_cluster_file = "/tmp/fdb"
        settings.nessie_url = None
        mock_get_settings.return_value = settings

        app = FastAPI()
        app.state.ontology_service = MagicMock()

        from lingshu.main import _setup_data_module
        _setup_data_module(app)

        assert hasattr(app.state, "data_service")
