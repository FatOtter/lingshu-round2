"""Data service: connection management + instance query pipeline."""

from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from lingshu.data.branch.nessie_client import NessieClient
from lingshu.data.connectors.postgresql import PostgreSQLConnector
from lingshu.data.models import Connection
from lingshu.data.pipeline.masking import apply_masking, build_masking_rules
from lingshu.data.pipeline.query_engine import QueryEngine
from lingshu.data.pipeline.schema_loader import SchemaLoader
from lingshu.data.pipeline.virtual_eval import apply_virtual_fields
from lingshu.data.repository.connection_repo import ConnectionRepository
from lingshu.data.schemas.responses import ConnectionResponse, ConnectionTestResponse
from lingshu.data.writeback.fdb_client import EditLogStore, make_entry
from lingshu.infra.context import get_tenant_id
from lingshu.infra.errors import AppError, ErrorCode
from lingshu.infra.models import Filter, SortSpec
from lingshu.infra.rid import generate_rid
from lingshu.ontology.interface import OntologyService


class DataServiceImpl:
    """Data service implementation."""

    def __init__(
        self,
        ontology_service: OntologyService,
        nessie_url: str | None = None,
        editlog_store: EditLogStore | None = None,
    ) -> None:
        self._ontology = ontology_service
        self._schema_loader = SchemaLoader(ontology_service)
        self._connectors: dict[str, PostgreSQLConnector] = {}
        self._nessie: NessieClient | None = (
            NessieClient(nessie_url) if nessie_url else None
        )
        self._edit_log_store = editlog_store or EditLogStore()

    # ── Connection Management ─────────────────────────────────────

    async def create_connection(
        self,
        display_name: str,
        conn_type: str,
        config: dict[str, Any],
        credentials: str | None,
        session: AsyncSession,
    ) -> ConnectionResponse:
        tenant_id = get_tenant_id()
        rid = generate_rid("conn")

        conn = Connection(
            rid=rid,
            tenant_id=tenant_id,
            display_name=display_name,
            type=conn_type,
            config=config,
            credentials=credentials,
            status="disconnected",
        )
        repo = ConnectionRepository(session)
        created = await repo.create(conn)
        await session.commit()
        return self._to_response(created)

    async def get_connection(
        self, rid: str, session: AsyncSession,
    ) -> ConnectionResponse:
        tenant_id = get_tenant_id()
        repo = ConnectionRepository(session)
        conn = await repo.get_by_rid(rid, tenant_id)
        if not conn:
            raise AppError(
                code=ErrorCode.DATA_SOURCE_NOT_FOUND,
                message=f"Connection {rid} not found",
            )
        return self._to_response(conn)

    async def update_connection(
        self,
        rid: str,
        updates: dict[str, Any],
        session: AsyncSession,
    ) -> ConnectionResponse:
        tenant_id = get_tenant_id()
        repo = ConnectionRepository(session)
        conn = await repo.update_fields(rid, tenant_id, **updates)
        if not conn:
            raise AppError(
                code=ErrorCode.DATA_SOURCE_NOT_FOUND,
                message=f"Connection {rid} not found",
            )
        await session.commit()

        # Invalidate cached connector
        self._connectors.pop(rid, None)
        return self._to_response(conn)

    async def delete_connection(
        self, rid: str, session: AsyncSession,
    ) -> None:
        tenant_id = get_tenant_id()
        repo = ConnectionRepository(session)
        deleted = await repo.delete(rid, tenant_id)
        if not deleted:
            raise AppError(
                code=ErrorCode.DATA_SOURCE_NOT_FOUND,
                message=f"Connection {rid} not found",
            )
        await session.commit()
        self._connectors.pop(rid, None)

    async def query_connections(
        self,
        session: AsyncSession,
        *,
        conn_type: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[ConnectionResponse], int]:
        tenant_id = get_tenant_id()
        repo = ConnectionRepository(session)
        conns, total = await repo.list_by_tenant(
            tenant_id, offset=offset, limit=limit, conn_type=conn_type
        )
        return [self._to_response(c) for c in conns], total

    async def test_connection(
        self, rid: str, session: AsyncSession,
    ) -> ConnectionTestResponse:
        tenant_id = get_tenant_id()
        repo = ConnectionRepository(session)
        conn = await repo.get_by_rid(rid, tenant_id)
        if not conn:
            raise AppError(
                code=ErrorCode.DATA_SOURCE_NOT_FOUND,
                message=f"Connection {rid} not found",
            )

        connector = self._get_or_create_connector(conn)
        result = await connector.test_connection()

        # Update connection status
        new_status = "connected" if result.success else "error"
        await repo.update_fields(
            rid, tenant_id,
            status=new_status,
            status_message=result.error,
            last_tested_at=datetime.utcnow(),
        )
        await session.commit()

        return ConnectionTestResponse(
            success=result.success,
            latency_ms=result.latency_ms,
            server_version=result.server_version,
            error=result.error,
        )

    # ── Instance Query Pipeline ───────────────────────────────────

    async def query_instances(
        self,
        type_rid: str,
        tenant_id: str,
        filters: list[Filter],
        sort: list[SortSpec],
        *,
        offset: int = 0,
        limit: int = 20,
    ) -> dict[str, Any]:
        """Full query pipeline: schema → query → virtual eval → masking."""
        schema = await self._schema_loader.get_schema(type_rid, tenant_id)

        if not schema.asset_mapping:
            raise AppError(
                code=ErrorCode.DATA_ASSET_NOT_MAPPED,
                message=f"No asset mapping configured for {type_rid}",
            )

        # Get connector from asset_mapping
        conn_rid = schema.asset_mapping.get("read_connection_id", "")
        table_path = schema.asset_mapping.get("read_asset_path", "")

        connector = await self._get_connector_by_rid(conn_rid, tenant_id)
        engine = QueryEngine(connector)

        result = await engine.query_instances(
            schema, table_path, filters, sort,
            offset=offset, limit=limit,
        )

        # Apply virtual fields
        rows = apply_virtual_fields(result.rows, schema.virtual_fields)

        # Apply masking
        masking_rules = build_masking_rules(schema.property_types)
        rows = apply_masking(rows, masking_rules)

        return {
            "rows": rows,
            "total": result.total,
            "columns": result.columns,
        }

    async def get_instance(
        self,
        type_rid: str,
        tenant_id: str,
        primary_key: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Get a single instance with virtual eval + masking."""
        schema = await self._schema_loader.get_schema(type_rid, tenant_id)

        if not schema.asset_mapping:
            raise AppError(
                code=ErrorCode.DATA_ASSET_NOT_MAPPED,
                message=f"No asset mapping configured for {type_rid}",
            )

        conn_rid = schema.asset_mapping.get("read_connection_id", "")
        table_path = schema.asset_mapping.get("read_asset_path", "")

        connector = await self._get_connector_by_rid(conn_rid, tenant_id)
        engine = QueryEngine(connector)

        row = await engine.get_instance(schema, table_path, primary_key)
        if not row:
            return None

        # Apply virtual fields
        rows = apply_virtual_fields([row], schema.virtual_fields)

        # Apply masking
        masking_rules = build_masking_rules(schema.property_types)
        rows = apply_masking(rows, masking_rules)

        return rows[0] if rows else None

    def invalidate_schema_cache(self, tenant_id: str) -> None:
        self._schema_loader.invalidate(tenant_id)

    # ── Overview ──────────────────────────────────────────────────

    async def get_overview(
        self, session: AsyncSession,
    ) -> dict[str, Any]:
        tenant_id = get_tenant_id()
        repo = ConnectionRepository(session)
        total = await repo.count_by_tenant(tenant_id)
        return {"connections": {"total": total}}

    # ── Branch Management ────────────────────────────────────────

    def _require_nessie(self) -> NessieClient:
        """Return Nessie client or raise if not configured."""
        if self._nessie is None:
            raise AppError(
                code=ErrorCode.DATA_BRANCH_UNAVAILABLE,
                message="Branch management is not configured (Nessie URL not set)",
            )
        return self._nessie

    async def list_branches(self) -> list[dict[str, Any]]:
        """List all data branches."""
        nessie = self._require_nessie()
        return await nessie.list_branches()

    async def get_branch(self, name: str) -> dict[str, Any]:
        """Get a data branch by name."""
        nessie = self._require_nessie()
        return await nessie.get_branch(name)

    async def create_branch(
        self, name: str, from_ref: str = "main",
    ) -> dict[str, Any]:
        """Create a new data branch from a reference."""
        nessie = self._require_nessie()
        return await nessie.create_branch(name, from_ref)

    async def delete_branch(self, name: str) -> None:
        """Delete a data branch (fetches hash automatically)."""
        nessie = self._require_nessie()
        branch = await nessie.get_branch(name)
        await nessie.delete_branch(name, branch["hash"])

    async def merge_branch(
        self, source: str, target: str = "main",
    ) -> dict[str, Any]:
        """Merge source data branch into target."""
        nessie = self._require_nessie()
        return await nessie.merge_branch(source, target)

    async def diff_branches(
        self, from_ref: str, to_ref: str,
    ) -> list[dict[str, Any]]:
        """Get diff between two data branches."""
        nessie = self._require_nessie()
        return await nessie.diff_branches(from_ref, to_ref)

    # ── Write-Back Pipeline ─────────────────────────────────────

    async def write_editlog(
        self,
        type_rid: str,
        primary_key: dict[str, Any],
        operation: str,
        field_values: dict[str, Any],
        user_id: str,
        session: AsyncSession,
        *,
        action_type_rid: str | None = None,
        branch: str = "main",
    ) -> str:
        """Write an edit log entry. Returns entry_id."""
        tenant_id = get_tenant_id()
        entry = make_entry(
            tenant_id=tenant_id,
            type_rid=type_rid,
            primary_key=primary_key,
            operation=operation,
            field_values=field_values,
            user_id=user_id,
            action_type_rid=action_type_rid,
            branch=branch,
        )
        entry_id = await self._edit_log_store.write(entry, session)
        await session.commit()
        return entry_id

    # ── Helpers ───────────────────────────────────────────────────

    def _get_or_create_connector(self, conn: Connection) -> PostgreSQLConnector:
        """Get or create a connector for a connection."""
        if conn.rid in self._connectors:
            return self._connectors[conn.rid]

        if conn.type == "postgresql":
            config = dict(conn.config)
            if conn.credentials:
                config["password"] = conn.credentials
            connector = PostgreSQLConnector(config)
            self._connectors[conn.rid] = connector
            return connector

        raise AppError(
            code=ErrorCode.DATA_SOURCE_UNREACHABLE,
            message=f"Unsupported connection type: {conn.type}",
        )

    async def _get_connector_by_rid(
        self, conn_rid: str, tenant_id: str,
    ) -> PostgreSQLConnector:
        """Get connector by connection RID (uses cached connectors)."""
        if conn_rid in self._connectors:
            return self._connectors[conn_rid]

        raise AppError(
            code=ErrorCode.DATA_SOURCE_NOT_FOUND,
            message=f"Connection {conn_rid} not found or not initialized",
        )

    def _to_response(self, conn: Connection) -> ConnectionResponse:
        return ConnectionResponse(
            rid=conn.rid,
            display_name=conn.display_name,
            type=conn.type,
            config=conn.config,
            status=conn.status,
            status_message=conn.status_message,
            last_tested_at=conn.last_tested_at,
            created_at=conn.created_at,
            updated_at=conn.updated_at,
        )
