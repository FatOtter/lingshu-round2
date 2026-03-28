"""PythonVenv engine: execute user Python scripts in an isolated subprocess."""

import asyncio
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

from lingshu.function.actions.engines.base import EngineResult
from lingshu.infra.errors import AppError, ErrorCode

_WRAPPER_TEMPLATE = """\
import json, sys

{user_script}

_input = json.loads(sys.stdin.read())
_params = _input["params"]
_context = _input["context"]
_result = execute(_params, _context)
print(json.dumps(_result))
"""

DEFAULT_TIMEOUT = 30


class PythonVenvEngine:
    """Execute user Python scripts in an isolated subprocess."""

    async def execute(
        self,
        config: dict[str, Any],
        resolved_params: dict[str, Any],
        instances: dict[str, dict[str, Any]],
    ) -> EngineResult:
        """Run a user-provided Python script in a subprocess.

        config keys:
          - script: str — Python source containing ``def execute(params, context)``
          - timeout: int — max seconds (default 30)
          - outputs: list — optional output descriptors for computed_values
        """
        script = config.get("script")
        if not script:
            raise AppError(
                code=ErrorCode.FUNCTION_EXECUTION_FAILED,
                message="PythonVenv engine requires a 'script' in config",
            )

        timeout = config.get("timeout", DEFAULT_TIMEOUT)
        outputs = config.get("outputs", [])

        wrapper_code = _WRAPPER_TEMPLATE.format(user_script=script)

        # Write wrapper to a temp file so the subprocess can execute it
        tmp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".py",
                delete=False,
            ) as tmp:
                tmp.write(wrapper_code)
                tmp_path = Path(tmp.name)

            stdin_payload = json.dumps({
                "params": resolved_params,
                "context": {"instances": instances},
            })

            proc = await asyncio.create_subprocess_exec(
                sys.executable, str(tmp_path),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(input=stdin_payload.encode()),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                raise AppError(
                    code=ErrorCode.FUNCTION_TIMEOUT,
                    message=f"Python script timed out after {timeout}s",
                )

            if proc.returncode != 0:
                stderr_text = stderr_bytes.decode(errors="replace").strip()
                raise AppError(
                    code=ErrorCode.FUNCTION_EXECUTION_FAILED,
                    message=f"Python script failed: {stderr_text}",
                )

            stdout_text = stdout_bytes.decode().strip()
            if not stdout_text:
                raise AppError(
                    code=ErrorCode.FUNCTION_EXECUTION_FAILED,
                    message="Python script produced no output",
                )

            try:
                result_data = json.loads(stdout_text)
            except json.JSONDecodeError as exc:
                raise AppError(
                    code=ErrorCode.FUNCTION_EXECUTION_FAILED,
                    message=f"Python script returned invalid JSON: {exc}",
                )

        finally:
            if tmp_path is not None:
                tmp_path.unlink(missing_ok=True)

        # Build computed_values from outputs config
        computed = _extract_computed_values(outputs, result_data)

        return EngineResult(data=result_data, computed_values=computed)


def _extract_computed_values(
    outputs: list[dict[str, Any]],
    result_data: Any,
) -> dict[str, Any]:
    """Map output definitions to values from the script result."""
    if not outputs or not isinstance(result_data, dict):
        return {}

    computed: dict[str, Any] = {}
    for output in outputs:
        name = output.get("name", "")
        field = output.get("field")
        if field and isinstance(result_data, dict):
            computed[name] = result_data.get(field)
        else:
            computed[name] = result_data
    return computed
