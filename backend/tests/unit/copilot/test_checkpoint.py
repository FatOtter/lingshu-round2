"""Tests for AsyncPostgresSaver checkpoint persistence."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from lingshu.copilot.checkpoint import AsyncPostgresSaver


def _make_row(**kwargs: Any) -> MagicMock:
    """Create a mock row with attribute access."""
    row = MagicMock()
    for k, v in kwargs.items():
        setattr(row, k, v)
    return row


@pytest.fixture
def saver() -> AsyncPostgresSaver:
    return AsyncPostgresSaver()


@pytest.fixture
def mock_db() -> AsyncMock:
    return AsyncMock()


# ── put ──────────────────────────────────────────────────────────


class TestPut:
    async def test_put_checkpoint(
        self, saver: AsyncPostgresSaver, mock_db: AsyncMock,
    ) -> None:
        await saver.put(
            mock_db,
            thread_id="thread-1",
            checkpoint_id="cp-1",
            checkpoint={"messages": ["hello"]},
            metadata={"step": 1},
        )
        mock_db.execute.assert_called_once()
        mock_db.flush.assert_called_once()

    async def test_put_with_parent(
        self, saver: AsyncPostgresSaver, mock_db: AsyncMock,
    ) -> None:
        await saver.put(
            mock_db,
            thread_id="thread-1",
            checkpoint_id="cp-2",
            parent_checkpoint_id="cp-1",
            checkpoint={"messages": ["hello", "world"]},
        )
        mock_db.execute.assert_called_once()
        call_args = mock_db.execute.call_args
        params = call_args[0][1]
        assert params["parent_checkpoint_id"] == "cp-1"


# ── get ──────────────────────────────────────────────────────────


class TestGet:
    async def test_get_latest_checkpoint(
        self, saver: AsyncPostgresSaver, mock_db: AsyncMock,
    ) -> None:
        now = datetime(2026, 3, 11, 12, 0, 0)
        row = _make_row(
            checkpoint_id="cp-1",
            parent_checkpoint_id=None,
            type="json",
            checkpoint={"messages": ["hello"]},
            metadata={"step": 1},
            created_at=now,
        )
        result = MagicMock()
        result.first.return_value = row
        mock_db.execute.return_value = result

        cp = await saver.get(mock_db, thread_id="thread-1")

        assert cp is not None
        assert cp["checkpoint_id"] == "cp-1"
        assert cp["checkpoint"] == {"messages": ["hello"]}
        assert cp["metadata"] == {"step": 1}

    async def test_get_specific_checkpoint(
        self, saver: AsyncPostgresSaver, mock_db: AsyncMock,
    ) -> None:
        row = _make_row(
            checkpoint_id="cp-2",
            parent_checkpoint_id="cp-1",
            type="json",
            checkpoint={"messages": ["hello", "world"]},
            metadata={},
            created_at=datetime(2026, 3, 11),
        )
        result = MagicMock()
        result.first.return_value = row
        mock_db.execute.return_value = result

        cp = await saver.get(
            mock_db, thread_id="thread-1", checkpoint_id="cp-2",
        )
        assert cp is not None
        assert cp["checkpoint_id"] == "cp-2"
        assert cp["parent_checkpoint_id"] == "cp-1"

    async def test_get_returns_none_when_missing(
        self, saver: AsyncPostgresSaver, mock_db: AsyncMock,
    ) -> None:
        result = MagicMock()
        result.first.return_value = None
        mock_db.execute.return_value = result

        cp = await saver.get(mock_db, thread_id="nonexistent")
        assert cp is None

    async def test_get_handles_string_json(
        self, saver: AsyncPostgresSaver, mock_db: AsyncMock,
    ) -> None:
        row = _make_row(
            checkpoint_id="cp-1",
            parent_checkpoint_id=None,
            type="json",
            checkpoint='{"key": "value"}',
            metadata='{"step": 2}',
            created_at=datetime(2026, 3, 11),
        )
        result = MagicMock()
        result.first.return_value = row
        mock_db.execute.return_value = result

        cp = await saver.get(mock_db, thread_id="thread-1")
        assert cp is not None
        assert cp["checkpoint"] == {"key": "value"}
        assert cp["metadata"] == {"step": 2}


# ── list ─────────────────────────────────────────────────────────


class TestList:
    async def test_list_checkpoints(
        self, saver: AsyncPostgresSaver, mock_db: AsyncMock,
    ) -> None:
        rows = [
            _make_row(
                checkpoint_id=f"cp-{i}",
                parent_checkpoint_id=f"cp-{i - 1}" if i > 0 else None,
                type="json",
                checkpoint={"step": i},
                metadata={},
                created_at=datetime(2026, 3, 11, i, 0, 0),
            )
            for i in range(3)
        ]
        result = MagicMock()
        result.fetchall.return_value = rows
        mock_db.execute.return_value = result

        items = await saver.list(mock_db, thread_id="thread-1", limit=10)
        assert len(items) == 3
        assert items[0]["checkpoint_id"] == "cp-0"
        assert items[2]["checkpoint"] == {"step": 2}

    async def test_list_empty(
        self, saver: AsyncPostgresSaver, mock_db: AsyncMock,
    ) -> None:
        result = MagicMock()
        result.fetchall.return_value = []
        mock_db.execute.return_value = result

        items = await saver.list(mock_db, thread_id="empty")
        assert items == []


# ── writes ───────────────────────────────────────────────────────


class TestWrites:
    async def test_put_writes(
        self, saver: AsyncPostgresSaver, mock_db: AsyncMock,
    ) -> None:
        writes = [
            ("task-1", "messages", {"role": "user", "content": "hi"}),
            ("task-2", "messages", {"role": "assistant", "content": "hello"}),
        ]
        await saver.put_writes(
            mock_db,
            thread_id="thread-1",
            checkpoint_id="cp-1",
            writes=writes,
        )
        assert mock_db.execute.call_count == 2
        mock_db.flush.assert_called_once()

    async def test_get_writes(
        self, saver: AsyncPostgresSaver, mock_db: AsyncMock,
    ) -> None:
        rows = [
            _make_row(
                task_id="task-1", idx=0, channel="messages",
                type="json", value={"role": "user"},
            ),
        ]
        result = MagicMock()
        result.fetchall.return_value = rows
        mock_db.execute.return_value = result

        writes = await saver.get_writes(
            mock_db, thread_id="thread-1", checkpoint_id="cp-1",
        )
        assert len(writes) == 1
        assert writes[0]["channel"] == "messages"
        assert writes[0]["value"] == {"role": "user"}


# ── delete ───────────────────────────────────────────────────────


class TestDelete:
    async def test_delete_thread(
        self, saver: AsyncPostgresSaver, mock_db: AsyncMock,
    ) -> None:
        await saver.delete_thread(mock_db, thread_id="thread-1")
        # Should delete from writes, blobs, and checkpoints (3 calls)
        assert mock_db.execute.call_count == 3
        mock_db.flush.assert_called_once()
