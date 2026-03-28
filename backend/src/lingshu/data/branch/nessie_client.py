"""Nessie REST API client for branch management."""

from typing import Any

import httpx

from lingshu.infra.errors import AppError, ErrorCode


class NessieClient:
    """Nessie REST API v2 client for data branch management."""

    def __init__(self, base_url: str = "http://localhost:19120/api/v2") -> None:
        self._base_url = base_url.rstrip("/")

    async def list_branches(self) -> list[dict[str, Any]]:
        """List all branches."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self._base_url}/trees",
                timeout=10.0,
            )
            resp.raise_for_status()
            data = resp.json()

        references = data.get("references", [])
        return [
            self._to_branch_dict(ref)
            for ref in references
            if ref.get("type") == "BRANCH"
        ]

    async def get_branch(self, name: str) -> dict[str, Any]:
        """Get branch details including hash."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self._base_url}/trees/{name}",
                timeout=10.0,
            )

        if resp.status_code == 404:
            raise AppError(
                code=ErrorCode.DATA_BRANCH_NOT_FOUND,
                message=f"Branch '{name}' not found",
            )
        resp.raise_for_status()
        return self._to_branch_dict(resp.json())

    async def create_branch(
        self, name: str, from_ref: str = "main",
    ) -> dict[str, Any]:
        """Create a new branch from a reference."""
        # First get the source branch hash
        source = await self.get_branch(from_ref)

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._base_url}/trees",
                json={
                    "type": "BRANCH",
                    "name": name,
                },
                params={"name": name, "type": "BRANCH"},
                headers={"Content-Type": "application/json"},
                timeout=10.0,
            )

        if resp.status_code == 409:
            raise AppError(
                code=ErrorCode.DATA_BRANCH_CONFLICT,
                message=f"Branch '{name}' already exists",
            )
        resp.raise_for_status()
        return self._to_branch_dict(resp.json())

    async def delete_branch(self, name: str, expected_hash: str) -> None:
        """Delete a branch (requires current hash for optimistic concurrency)."""
        if name == "main":
            raise AppError(
                code=ErrorCode.DATA_BRANCH_CONFLICT,
                message="Cannot delete the main branch",
            )

        async with httpx.AsyncClient() as client:
            resp = await client.delete(
                f"{self._base_url}/trees/{name}",
                headers={"If-Match": f'"{expected_hash}"'},
                timeout=10.0,
            )

        if resp.status_code == 404:
            raise AppError(
                code=ErrorCode.DATA_BRANCH_NOT_FOUND,
                message=f"Branch '{name}' not found",
            )
        if resp.status_code == 409:
            raise AppError(
                code=ErrorCode.DATA_BRANCH_CONFLICT,
                message=f"Branch '{name}' was modified concurrently (hash mismatch)",
            )
        resp.raise_for_status()

    async def merge_branch(
        self, source: str, target: str = "main",
    ) -> dict[str, Any]:
        """Merge source branch into target."""
        source_branch = await self.get_branch(source)
        target_branch = await self.get_branch(target)

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._base_url}/trees/{target}/merge",
                json={
                    "fromRefName": source,
                    "fromHash": source_branch["hash"],
                },
                headers={
                    "Content-Type": "application/json",
                    "If-Match": f'"{target_branch["hash"]}"',
                },
                timeout=30.0,
            )

        if resp.status_code == 409:
            raise AppError(
                code=ErrorCode.DATA_BRANCH_CONFLICT,
                message=f"Merge conflict: cannot merge '{source}' into '{target}'",
            )
        resp.raise_for_status()
        return resp.json()

    async def diff_branches(
        self, from_ref: str, to_ref: str,
    ) -> list[dict[str, Any]]:
        """Get diff between two branches."""
        # Validate both branches exist
        await self.get_branch(from_ref)
        await self.get_branch(to_ref)

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self._base_url}/trees/{from_ref}/diff/{to_ref}",
                timeout=10.0,
            )
            resp.raise_for_status()
            data = resp.json()

        return data.get("diffs", [])

    @staticmethod
    def _to_branch_dict(ref: dict[str, Any]) -> dict[str, Any]:
        """Convert a Nessie reference to a clean branch dict."""
        return {
            "name": ref.get("name", ""),
            "hash": ref.get("hash", ""),
            "metadata": ref.get("metadata"),
        }
