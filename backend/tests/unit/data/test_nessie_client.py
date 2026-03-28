"""Unit tests for Nessie REST API client."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from lingshu.data.branch.nessie_client import NessieClient
from lingshu.infra.errors import AppError, ErrorCode


@pytest.fixture
def client() -> NessieClient:
    return NessieClient(base_url="http://nessie-test:19120/api/v2")


def _mock_response(
    status_code: int = 200,
    json_data: dict | list | None = None,
) -> httpx.Response:
    """Build a fake httpx.Response."""
    resp = httpx.Response(
        status_code=status_code,
        json=json_data,
        request=httpx.Request("GET", "http://nessie-test:19120/api/v2/trees"),
    )
    return resp


# ── list_branches ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_branches_returns_branches(client: NessieClient) -> None:
    mock_resp = _mock_response(
        json_data={
            "references": [
                {"type": "BRANCH", "name": "main", "hash": "abc123"},
                {"type": "BRANCH", "name": "feature-1", "hash": "def456"},
                {"type": "TAG", "name": "v1.0", "hash": "ghi789"},
            ],
        },
    )
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
        branches = await client.list_branches()

    assert len(branches) == 2
    assert branches[0]["name"] == "main"
    assert branches[0]["hash"] == "abc123"
    assert branches[1]["name"] == "feature-1"


@pytest.mark.asyncio
async def test_list_branches_empty(client: NessieClient) -> None:
    mock_resp = _mock_response(json_data={"references": []})
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
        branches = await client.list_branches()

    assert branches == []


# ── get_branch ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_branch_success(client: NessieClient) -> None:
    mock_resp = _mock_response(
        json_data={"name": "main", "hash": "abc123", "metadata": None},
    )
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
        branch = await client.get_branch("main")

    assert branch["name"] == "main"
    assert branch["hash"] == "abc123"


@pytest.mark.asyncio
async def test_get_branch_not_found(client: NessieClient) -> None:
    mock_resp = _mock_response(status_code=404, json_data={"message": "not found"})
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
        with pytest.raises(AppError) as exc_info:
            await client.get_branch("nonexistent")

    assert exc_info.value.code == ErrorCode.DATA_BRANCH_NOT_FOUND


# ── create_branch ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_branch_success(client: NessieClient) -> None:
    get_resp = _mock_response(
        json_data={"name": "main", "hash": "abc123"},
    )
    create_resp = _mock_response(
        status_code=200,
        json_data={"name": "feature-x", "hash": "new789"},
    )

    async def mock_get(*args, **kwargs):
        return get_resp

    async def mock_post(*args, **kwargs):
        return create_resp

    with (
        patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=mock_get),
        patch("httpx.AsyncClient.post", new_callable=AsyncMock, side_effect=mock_post),
    ):
        branch = await client.create_branch("feature-x", "main")

    assert branch["name"] == "feature-x"
    assert branch["hash"] == "new789"


@pytest.mark.asyncio
async def test_create_branch_conflict(client: NessieClient) -> None:
    get_resp = _mock_response(
        json_data={"name": "main", "hash": "abc123"},
    )
    conflict_resp = _mock_response(
        status_code=409,
        json_data={"message": "conflict"},
    )

    async def mock_get(*args, **kwargs):
        return get_resp

    async def mock_post(*args, **kwargs):
        return conflict_resp

    with (
        patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=mock_get),
        patch("httpx.AsyncClient.post", new_callable=AsyncMock, side_effect=mock_post),
    ):
        with pytest.raises(AppError) as exc_info:
            await client.create_branch("existing-branch", "main")

    assert exc_info.value.code == ErrorCode.DATA_BRANCH_CONFLICT


# ── delete_branch ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_branch_success(client: NessieClient) -> None:
    delete_resp = _mock_response(status_code=204, json_data=None)
    # Response with 204 has no body
    delete_resp = httpx.Response(
        status_code=204,
        request=httpx.Request("DELETE", "http://nessie-test:19120/api/v2/trees/feature-x"),
    )
    with patch("httpx.AsyncClient.delete", new_callable=AsyncMock, return_value=delete_resp):
        await client.delete_branch("feature-x", "abc123")


@pytest.mark.asyncio
async def test_delete_branch_not_found(client: NessieClient) -> None:
    resp = _mock_response(status_code=404, json_data={"message": "not found"})
    with patch("httpx.AsyncClient.delete", new_callable=AsyncMock, return_value=resp):
        with pytest.raises(AppError) as exc_info:
            await client.delete_branch("gone", "abc123")

    assert exc_info.value.code == ErrorCode.DATA_BRANCH_NOT_FOUND


@pytest.mark.asyncio
async def test_delete_branch_conflict(client: NessieClient) -> None:
    resp = _mock_response(status_code=409, json_data={"message": "conflict"})
    with patch("httpx.AsyncClient.delete", new_callable=AsyncMock, return_value=resp):
        with pytest.raises(AppError) as exc_info:
            await client.delete_branch("stale", "old_hash")

    assert exc_info.value.code == ErrorCode.DATA_BRANCH_CONFLICT


@pytest.mark.asyncio
async def test_delete_main_branch_rejected(client: NessieClient) -> None:
    with pytest.raises(AppError) as exc_info:
        await client.delete_branch("main", "abc123")

    assert exc_info.value.code == ErrorCode.DATA_BRANCH_CONFLICT
    assert "main" in exc_info.value.message


# ── merge_branch ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_merge_branch_success(client: NessieClient) -> None:
    call_count = 0

    async def mock_get(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _mock_response(json_data={"name": "feature-x", "hash": "src111"})
        return _mock_response(json_data={"name": "main", "hash": "tgt222"})

    merge_resp = _mock_response(
        json_data={"resultantTargetHash": "merged333"},
    )

    with (
        patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=mock_get),
        patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=merge_resp),
    ):
        result = await client.merge_branch("feature-x", "main")

    assert result["resultantTargetHash"] == "merged333"


@pytest.mark.asyncio
async def test_merge_branch_conflict(client: NessieClient) -> None:
    call_count = 0

    async def mock_get(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _mock_response(json_data={"name": "feature-x", "hash": "src111"})
        return _mock_response(json_data={"name": "main", "hash": "tgt222"})

    conflict_resp = _mock_response(status_code=409, json_data={"message": "conflict"})

    with (
        patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=mock_get),
        patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=conflict_resp),
    ):
        with pytest.raises(AppError) as exc_info:
            await client.merge_branch("feature-x", "main")

    assert exc_info.value.code == ErrorCode.DATA_BRANCH_CONFLICT


# ── diff_branches ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_diff_branches_success(client: NessieClient) -> None:
    call_count = 0

    async def mock_get(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        url = str(kwargs.get("url", args[0] if args else ""))
        if "diff" in url:
            return _mock_response(
                json_data={
                    "diffs": [
                        {"key": {"elements": ["table1"]}, "type": "ADD"},
                        {"key": {"elements": ["table2"]}, "type": "MODIFY"},
                    ],
                },
            )
        # Branch validation calls
        if call_count == 1:
            return _mock_response(json_data={"name": "feature-x", "hash": "aaa"})
        return _mock_response(json_data={"name": "main", "hash": "bbb"})

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=mock_get):
        diffs = await client.diff_branches("feature-x", "main")

    assert len(diffs) == 2
    assert diffs[0]["type"] == "ADD"


@pytest.mark.asyncio
async def test_diff_branches_source_not_found(client: NessieClient) -> None:
    not_found = _mock_response(status_code=404, json_data={"message": "not found"})
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=not_found):
        with pytest.raises(AppError) as exc_info:
            await client.diff_branches("missing", "main")

    assert exc_info.value.code == ErrorCode.DATA_BRANCH_NOT_FOUND


# ── _to_branch_dict ──────────────────────────────────────────────


def test_to_branch_dict_minimal() -> None:
    result = NessieClient._to_branch_dict({"name": "dev", "hash": "xyz"})
    assert result == {"name": "dev", "hash": "xyz", "metadata": None}


def test_to_branch_dict_with_metadata() -> None:
    result = NessieClient._to_branch_dict({
        "name": "dev",
        "hash": "xyz",
        "metadata": {"author": "test"},
    })
    assert result["metadata"] == {"author": "test"}
