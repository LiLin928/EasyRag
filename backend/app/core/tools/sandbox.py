\"\"\"代码沙箱服务 - Docker隔离执行环境。\"\"\"
import asyncio
import json
import tempfile
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

from app.exceptions import BizException, ErrorCode


class SandboxLanguage(Enum):
    PYTHON = \"python\"
    NODEJS = \"nodejs\"


@dataclass
class SandboxConfig:
    memory_limit_mb: int = 512
    cpu_limit: float = 1.0
    timeout_seconds: int = 30
    max_output_size: int = 1048576
    network_disabled: bool = True


@dataclass
class SandboxResult:
    success: bool
    stdout: str
    stderr: str
    exit_code: int
    execution_time_ms: float
    error: Optional[str] = None


class CodeSandbox:
    def __init__(self, config: Optional[SandboxConfig] = None):
        self.config = config or SandboxConfig()
        self._work_dirs: dict = {}

    async def _create_container(self, language: SandboxLanguage, code: str, inputs: Optional[dict] = None) -> str:
        work_dir = tempfile.mkdtemp(prefix=\"sandbox_\")
        if language == SandboxLanguage.PYTHON:
            code_file = Path(work_dir) / \"main.py\"
            image = \"python:3.10-alpine\"
            cmd = [\"python\", \"/code/main.py\"]
        else:
            code_file = Path(work_dir) / \"main.js\"
            image = \"node:18-alpine\"
            cmd = [\"node\", \"/code/main.js\"]
        code_file.write_text(code, encoding=\"utf-8\")
        if inputs:
            input_file = Path(work_dir) / \"input.json\"
            input_file.write_text(json.dumps(inputs), encoding=\"utf-8\")
        docker_cmd = [
            \"docker\", \"run\", \"-d\", \"--rm\", \"--read-only\",
            f\"--memory={self.config.memory_limit_mb}m\",
            f\"--cpus={self.config.cpu_limit}\",
            \"-v\", f\"{work_dir}:/code:ro\", \"-w\", \"/code\",
            \"--network=none\", \"--cap-drop=ALL\",
            \"--security-opt=no-new-privileges:true\", \"--pids-limit=64\",
            image
        ] + cmd
        proc = await asyncio.create_subprocess_exec(*docker_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise BizException(ErrorCode.DEPENDENCY_DOWN, f\"Failed to create container: {stderr.decode()}\")
        container_id = stdout.decode().strip()
        self._work_dirs[container_id] = work_dir
        return container_id

    async def _wait_container(self, container_id: str, timeout: int) -> tuple[int, str, str]:
        start_time = time.time()
        while time.time() - start_time < timeout:
            proc = await asyncio.create_subprocess_exec(\"docker\", \"inspect\", \"-f\", \"{{.State.Status}}\", container_id, stdout=asyncio.subprocess.PIPE)
            stdout, _ = await proc.communicate()
            status = stdout.decode().strip()
            if status == \"exited\":
                proc = await asyncio.create_subprocess_exec(\"docker\", \"inspect\", \"-f\", \"{{.State.ExitCode}}\", container_id, stdout=asyncio.subprocess.PIPE)
                exit_code = int((await proc.communicate())[0].decode().strip())
                proc = await asyncio.create_subprocess_exec(\"docker\", \"logs\", container_id, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                stdout, stderr = await proc.communicate()
                return exit_code, stdout.decode(), stderr.decode()
            elif status in [\"dead\", \"removing\"]:
                return -1, \"\", f\"Container {status}\"
            await asyncio.sleep(0.1)
        await asyncio.create_subprocess_exec(\"docker\", \"stop\", \"-t\", \"1\", container_id)
        return -1, \"\", \"Execution timeout\"

    async def _cleanup_container(self, container_id: str):
        try:
            await asyncio.create_subprocess_exec(\"docker\", \"stop\", \"-t\", \"1\", container_id, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
            await asyncio.create_subprocess_exec(\"docker\", \"rm\", \"-f\", container_id, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
        except Exception:
            pass
        if container_id in self._work_dirs:
            import shutil
            shutil.rmtree(self._work_dirs[container_id], ignore_errors=True)
            del self._work_dirs[container_id]

    async def execute(self, language, code: str, inputs: Optional[dict] = None, config: Optional[SandboxConfig] = None) -> SandboxResult:
        exec_config = config or self.config
        if isinstance(language, str):
            try:
                language = SandboxLanguage(language.lower())
            except ValueError:
                raise BizException(ErrorCode.PARAM_ERROR, f\"Unsupported language: {language}\")
        if len(code) > 100000:
            raise BizException(ErrorCode.PARAM_ERROR, \"Code size exceeds 100KB limit\")
        dangerous = [\"__import__\", \"eval(\", \"exec(\", \"os.system\", \"subprocess.\", \"require('child_process')\"]
        for p in dangerous:
            if p in code:
                raise BizException(ErrorCode.PARAM_ERROR, f\"Dangerous operation: {p}\")
        container_id = None
        start_time = time.time()
        try:
            container_id = await self._create_container(language, code, inputs)
            exit_code, stdout, stderr = await self._wait_container(container_id, exec_config.timeout_seconds)
            execution_time_ms = (time.time() - start_time) * 1000
            if len(stdout) > exec_config.max_output_size:
                stdout = stdout[:exec_config.max_output_size] + \"\\n[Output truncated]\"
            return SandboxResult(success=exit_code == 0, stdout=stdout, stderr=stderr, exit_code=exit_code, execution_time_ms=execution_time_ms, error=None if exit_code == 0 else stderr[:1000])
        except Exception as e:
            return SandboxResult(success=False, stdout=\"\", stderr=str(e), exit_code=-1, execution_time_ms=(time.time() - start_time) * 1000, error=str(e))
        finally:
            if container_id:
                await self._cleanup_container(container_id)

    async def health_check(self) -> dict:
        try:
            proc = await asyncio.create_subprocess_exec(\"docker\", \"version\", \"-f\", \"{{.Server.Version}}\", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            stdout, stderr = await proc.communicate()
            if proc.returncode == 0:
                return {\"status\": \"healthy\", \"docker_version\": stdout.decode().strip(), \"supported_languages\": [\"python\", \"nodejs\"]}
            return {\"status\": \"unhealthy\", \"error\": stderr.decode().strip()}
        except Exception as e:
            return {\"status\": \"error\", \"error\": str(e)}


_sandbox_instance: Optional[CodeSandbox] = None

def get_sandbox(config: Optional[SandboxConfig] = None) -> CodeSandbox:
    global _sandbox_instance
    if _sandbox_instance is None:
        _sandbox_instance = CodeSandbox(config)
    return _sandbox_instance

async def execute_code(language: str, code: str, inputs: Optional[dict] = None, timeout: int = 30, memory_limit_mb: int = 512) -> SandboxResult:
    config = SandboxConfig(timeout_seconds=timeout, memory_limit_mb=memory_limit_mb)
    return await get_sandbox(config).execute(language, code, inputs, config)
