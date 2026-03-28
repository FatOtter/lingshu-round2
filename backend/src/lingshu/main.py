"""FastAPI application entry point."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from lingshu.config import get_settings
from lingshu.infra.database import close_db, get_session, init_db
from lingshu.infra.errors import register_exception_handlers
from lingshu.infra.graph_db import close_graph_db, init_graph_db
from lingshu.infra.redis import close_redis, get_redis, init_redis


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Application lifespan: initialize and cleanup resources."""
    settings = get_settings()

    # Init storage connections
    await init_db(settings.database_url)
    await init_graph_db(settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password)
    await init_redis(settings.redis_url)

    # Initialize Setting module services (requires Redis)
    _setup_setting_module(app, settings)

    # Initialize Ontology module services (requires Neo4j + Redis)
    _setup_ontology_module(app)

    # Initialize Data module services (requires OntologyService)
    _setup_data_module(app)

    # Initialize Function module services (requires OntologyService + DataService)
    _setup_function_module(app)

    # Initialize Copilot module services (requires FunctionService)
    _setup_copilot_module(app)

    # Run seed (pass enforcer for RBAC policy seeding)
    from lingshu.setting.seed import run_seed

    enforcer = app.state.auth_enforcer
    async for session in get_session():
        await run_seed(session, settings, enforcer)

    yield

    await close_redis()
    await close_graph_db()
    await close_db()


def _setup_setting_module(app: FastAPI, settings: object) -> None:
    """Wire up Setting module: provider, enforcer, service, middleware."""
    from lingshu.config import Settings

    assert isinstance(settings, Settings)

    from lingshu.setting.auth.provider import BuiltinProvider
    from lingshu.setting.authz.enforcer import PermissionEnforcer
    from lingshu.setting.router import set_service
    from lingshu.setting.service import SettingServiceImpl

    redis = get_redis()
    provider = BuiltinProvider(settings, redis)
    enforcer = PermissionEnforcer(settings=settings)
    setting_service = SettingServiceImpl(
        provider=provider,
        enforcer=enforcer,
        refresh_ttl=settings.refresh_token_ttl,
    )
    set_service(setting_service)

    # Store provider and enforcer on app for middleware and seed access
    app.state.auth_provider = provider
    app.state.auth_enforcer = enforcer
    app.state.auth_dev_mode = settings.is_dev


def _setup_data_module(app: FastAPI) -> None:
    """Wire up Data module: service, router."""
    from lingshu.config import get_settings
    from lingshu.data.router import set_data_service
    from lingshu.data.service import DataServiceImpl
    from lingshu.data.writeback.fdb_client import create_editlog_store

    settings = get_settings()
    ontology_service = app.state.ontology_service
    editlog_store = create_editlog_store(
        settings.editlog_backend,
        cluster_file=settings.fdb_cluster_file,
    )
    data_service = DataServiceImpl(
        ontology_service=ontology_service,
        nessie_url=settings.nessie_url,
        editlog_store=editlog_store,
    )
    set_data_service(data_service)

    app.state.data_service = data_service


def _setup_ontology_module(app: FastAPI) -> None:
    """Wire up Ontology module: graph_repo, service, router."""
    from lingshu.infra.graph_db import get_driver
    from lingshu.ontology.repository.graph_repo import GraphRepository
    from lingshu.ontology.router import set_ontology_service
    from lingshu.ontology.service import OntologyServiceImpl

    redis = get_redis()
    driver = get_driver()
    graph_repo = GraphRepository(driver)
    ontology_service = OntologyServiceImpl(graph_repo=graph_repo, redis=redis)
    set_ontology_service(ontology_service)

    app.state.ontology_service = ontology_service


def _setup_copilot_module(app: FastAPI) -> None:
    """Wire up Copilot module: service, router."""
    from lingshu.config import get_settings
    from lingshu.copilot.router import set_copilot_service
    from lingshu.copilot.service import CopilotServiceImpl

    settings = get_settings()
    function_service = app.state.function_service
    copilot_service = CopilotServiceImpl(
        function_service=function_service,
        settings=settings,
    )
    set_copilot_service(copilot_service)

    app.state.copilot_service = copilot_service


def _setup_function_module(app: FastAPI) -> None:
    """Wire up Function module: service, router."""
    from lingshu.function.router import set_function_service
    from lingshu.function.service import FunctionServiceImpl

    ontology_service = app.state.ontology_service
    data_service = app.state.data_service
    function_service = FunctionServiceImpl(
        ontology_service=ontology_service,
        data_service=data_service,
    )
    set_function_service(function_service)

    app.state.function_service = function_service


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    settings = get_settings()

    # Disable API docs in production to avoid leaking schema
    docs_url = None if settings.is_production else "/docs"
    openapi_url = None if settings.is_production else "/openapi.json"
    redoc_url = None if settings.is_production else "/redoc"

    app = FastAPI(
        title="LingShu",
        description="Ontology-centric Data Operating System",
        version="0.1.0",
        lifespan=lifespan,
        docs_url=docs_url,
        openapi_url=openapi_url,
        redoc_url=redoc_url,
    )

    # Exception handlers
    register_exception_handlers(app)

    # Auth middleware (added first → inner layer in LIFO)
    # Provider is resolved lazily from request.app.state during lifespan
    from lingshu.setting.auth.middleware import AuthMiddleware

    app.add_middleware(AuthMiddleware, dev_mode=settings.is_dev)

    # CORS (added last → outermost layer in LIFO, wraps everything including AuthMiddleware)
    # Always use configured origins — in production, set LINGSHU_CORS_ORIGINS explicitly
    cors_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routers
    from lingshu.copilot.router import router as copilot_router
    from lingshu.data.router import router as data_router
    from lingshu.function.router import router as function_router
    from lingshu.ontology.router import router as ontology_router
    from lingshu.setting.router import router as setting_router

    app.include_router(setting_router)
    app.include_router(ontology_router)
    app.include_router(data_router)
    app.include_router(function_router)
    app.include_router(copilot_router)

    @app.get("/health")
    async def health_check() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
