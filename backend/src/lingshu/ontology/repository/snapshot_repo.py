"""Snapshot repository: PostgreSQL CRUD for snapshots and active_pointers."""

from datetime import datetime
from typing import Any

from sqlalchemy import func as sa_func
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from lingshu.ontology.models import ActivePointer, Snapshot


class SnapshotRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, snapshot: Snapshot) -> Snapshot:
        self._session.add(snapshot)
        await self._session.flush()
        return snapshot

    async def get_by_id(self, snapshot_id: str) -> Snapshot | None:
        result = await self._session.execute(
            select(Snapshot).where(Snapshot.snapshot_id == snapshot_id)
        )
        return result.scalar_one_or_none()

    async def list_by_tenant(
        self,
        tenant_id: str,
        *,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[Snapshot], int]:
        base = select(Snapshot).where(Snapshot.tenant_id == tenant_id)
        count_result = await self._session.execute(
            select(sa_func.count()).select_from(base.subquery())
        )
        total: int = count_result.scalar_one()
        result = await self._session.execute(
            base.order_by(Snapshot.created_at.desc()).offset(offset).limit(limit)
        )
        return list(result.scalars().all()), total

    async def get_active_pointer(self, tenant_id: str) -> ActivePointer | None:
        result = await self._session.execute(
            select(ActivePointer).where(ActivePointer.tenant_id == tenant_id)
        )
        return result.scalar_one_or_none()

    async def set_active_pointer(
        self, tenant_id: str, snapshot_id: str
    ) -> ActivePointer:
        existing = await self.get_active_pointer(tenant_id)
        if existing:
            await self._session.execute(
                update(ActivePointer)
                .where(ActivePointer.tenant_id == tenant_id)
                .values(snapshot_id=snapshot_id, updated_at=datetime.utcnow())
            )
            await self._session.flush()
            return ActivePointer(
                tenant_id=tenant_id,
                snapshot_id=snapshot_id,
                updated_at=datetime.utcnow(),
            )
        pointer = ActivePointer(tenant_id=tenant_id, snapshot_id=snapshot_id)
        self._session.add(pointer)
        await self._session.flush()
        return pointer

    async def get_diff(
        self,
        snapshot_id: str,
        current_snapshot_id: str | None,
    ) -> dict[str, Any]:
        """Get diff between a snapshot and the current active snapshot."""
        snap = await self.get_by_id(snapshot_id)
        if not snap:
            return {"changes": {}}

        current_changes: dict[str, Any] = {}
        if current_snapshot_id:
            current = await self.get_by_id(current_snapshot_id)
            if current:
                current_changes = current.entity_changes

        return {
            "snapshot_changes": snap.entity_changes,
            "current_changes": current_changes,
        }

    async def get_field_diff(
        self,
        snapshot_id_a: str,
        snapshot_id_b: str,
    ) -> dict[str, dict[str, Any]]:
        """Compare entity_data between two snapshots at the field level.

        Returns a dict keyed by entity RID, each containing:
          - added: fields present in B but not A
          - removed: fields present in A but not B
          - changed: fields present in both but with different values
            (each entry has 'old' and 'new')
        """
        snap_a = await self.get_by_id(snapshot_id_a)
        snap_b = await self.get_by_id(snapshot_id_b)

        data_a: dict[str, dict[str, Any]] = (snap_a.entity_data or {}) if snap_a else {}
        data_b: dict[str, dict[str, Any]] = (snap_b.entity_data or {}) if snap_b else {}

        all_rids = set(data_a.keys()) | set(data_b.keys())
        result: dict[str, dict[str, Any]] = {}

        for rid in all_rids:
            fields_a = data_a.get(rid, {})
            fields_b = data_b.get(rid, {})
            diff = _compute_field_diff(fields_a, fields_b)
            if diff["added"] or diff["removed"] or diff["changed"]:
                result[rid] = diff

        return result


def _compute_field_diff(
    fields_a: dict[str, Any],
    fields_b: dict[str, Any],
) -> dict[str, Any]:
    """Compute field-level diff between two entity data dicts."""
    all_keys = set(fields_a.keys()) | set(fields_b.keys())
    added: dict[str, Any] = {}
    removed: dict[str, Any] = {}
    changed: dict[str, Any] = {}

    for key in all_keys:
        in_a = key in fields_a
        in_b = key in fields_b
        if in_b and not in_a:
            added[key] = fields_b[key]
        elif in_a and not in_b:
            removed[key] = fields_a[key]
        elif fields_a[key] != fields_b[key]:
            changed[key] = {"old": fields_a[key], "new": fields_b[key]}

    return {"added": added, "removed": removed, "changed": changed}
