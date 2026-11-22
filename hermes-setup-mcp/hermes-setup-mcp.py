"""Local stdio MCP server for SSH and sudo on dedicated Ubuntu hosts."""

from __future__ import annotations

import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import shutil
import subprocess

import keyring
from mcp.server.fastmcp import FastMCP

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "hosts.json"
PAYLOADS = ROOT / "payloads"
SERVICE = "hermes-setup-mcp-sudo"
MAX_OUTPUT_CHARS = 18_000
VALID_PATH = re.compile(r"^/[a-zA-Z0-9._/-]+$")
VALID_RELATIVE = re.compile(r"^[a-zA-Z0-9._/-]+$")

mcp = FastMCP(
    "hermes-setup-mcp",
    instructions=(
        "Provision configured Ubuntu hosts over SSH with a locally stored sudo password. "
        "Use only configured host aliases. Never request or display credentials. "
        "Read and follow the project's runbook and mise.toml; verify after changes. "
        "Only use ssh_exec with sudo=True for commands requiring Linux root. "
        "Unrestricted sudo execution is powerful and not a security sandbox."
    ),
)


def _hosts() -> dict:
    data = json.loads(CONFIG.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("hosts.json must contain a JSON object")
    return data


def _host(alias: str) -> dict:
    config = _hosts().get(alias)
    if not isinstance(config, dict):
        raise ValueError("Unknown host alias; see list_hosts")
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", alias):
        raise ValueError("Invalid SSH alias")
    remote_dir = config.get("remote_dir")
    if not isinstance(remote_dir, str) or not VALID_PATH.fullmatch(remote_dir):
        raise ValueError("Invalid remote_dir in hosts.json")
    if ".." in PurePosixPath(remote_dir).parts:
        raise ValueError("Unsafe remote_dir in hosts.json")
    return config


def _openssh(name: str) -> str:
    # Prefer the built-in Windows OpenSSH client, so the Windows ssh-agent is used.
    if os.name == "nt":
        binary = Path(os.environ["WINDIR"]) / "System32" / "OpenSSH" / f"{name}.exe"
        if not binary.is_file():
            raise RuntimeError(f"Windows OpenSSH {name}.exe not installed")
        return str(binary)
    binary = shutil.which(name)
    if not binary:
        raise RuntimeError(f"Cannot find {name}")
    return binary


def _options() -> list[str]:
    return [
        "-o", "BatchMode=yes",                  # Disable interactive SSH prompts
        "-o", "StrictHostKeyChecking=yes",      # Never auto-trust a new server key
        "-o", "ForwardAgent=no",                # Do not forward the Windows agent
        "-o", "ClearAllForwardings=yes",
        "-o", "ConnectTimeout=12",
        "-o", "ConnectionAttempts=1",
    ]


def _trim_and_redact(output: str, password: str | None = None) -> str:
    if password:
        output = output.replace(password, "[REDACTED]")
    if len(output) > MAX_OUTPUT_CHARS:
        return output[:MAX_OUTPUT_CHARS] + "\n[TRUNCATED]"
    return output


def _sudo_password(alias: str) -> str:
    """Read only from the native Windows Generic Credential backend."""
    if os.name != "nt":
        raise RuntimeError("This MCP server requires native Windows Python, not WSL")
    from keyring.backends.Windows import WinVaultKeyring
    keyring.set_keyring(WinVaultKeyring())
    password = keyring.get_password(SERVICE, alias)
    if password is None:
        raise RuntimeError("Sudo credential is absent. Run credentials.py set in your own terminal.")
    if not password or "\n" in password or "\r" in password:
        raise RuntimeError("Invalid stored sudo credential")
    return password


def _run(alias: str, command: str, *, sudo: bool = False, timeout_seconds: int = 600) -> dict:
    _host(alias)
    if not command.strip() or len(command) > 16_000:
        raise ValueError("Command must be nonempty and at most 16,000 chars")
    if not 1 <= timeout_seconds <= 1800:
        raise ValueError("timeout_seconds must be between 1 and 1800")

    password = None
    remote_command = "/bin/bash -c " + shlex.quote(command)
    if sudo:
        password = _sudo_password(alias)
        # -k forces sudo to authenticate anew rather than use a cached timestamp.
        # First action inside the elevated shell is to close stdin, so even if
        # sudo does not consume the supplied line, the actual command cannot read it.
        root_command = "exec </dev/null; " + command
        remote_command = (
            "sudo -k -S -p '' -- /bin/bash -c " + shlex.quote(root_command)
        )

    argv = [_openssh("ssh"), "-T", *_options(), alias, remote_command]
    # Do not put the password in argv, environment variables, or log messages.
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    try:
        completed = subprocess.run(
            argv, input=(password + "\n" if password is not None else ""),
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout_seconds, check=False, creationflags=creationflags,
        )
    except subprocess.TimeoutExpired:
        return {
            "host": alias, "timed_out": True, "exit_code": None,
            "note": "Local SSH timed out. The remote process may still be running; check state before retrying.",
        }
    except OSError as exc:
        return {"host": alias, "exit_code": None, "error": f"SSH could not start: {type(exc).__name__}"}

    return {
        "host": alias,
        "exit_code": completed.returncode,
        "stdout": _trim_and_redact(completed.stdout, password),
        "stderr": _trim_and_redact(completed.stderr, password),
    }


@mcp.tool()
def list_hosts() -> list[str]:
    """List explicitly allowed SSH host aliases. No credentials are returned."""
    return sorted(_hosts().keys())


@mcp.tool()
def ssh_exec(host: str, command: str, sudo: bool = False, timeout_seconds: int = 600) -> dict:
    """Run a Bash command on a configured SSH host. sudo=True uses the stored password.

    Full Linux root command execution is available when sudo=True. This is NOT
    a restricted command executor. Use idempotent commands when possible.
    Commands requiring interactive input cannot run. Results may be truncated.
    """
    return _run(host, command, sudo=sudo, timeout_seconds=timeout_seconds)


@mcp.tool()
def ssh_upload(host: str, relative_path: str) -> dict:
    """Upload a file from the local payloads/ directory to the host's remote_dir.

    Pass only a relative path such as 'mise.toml' or 'scripts/install.sh'.
    Missing remote subdirectories are created as the normal SSH user.
    """
    config = _host(host)
    if (
        not relative_path
        or not VALID_RELATIVE.fullmatch(relative_path)
        or any(part in ("", ".", "..") for part in relative_path.split("/"))
    ):
        raise ValueError("Unsafe relative_path")
    local_root = PAYLOADS.resolve()
    local_path = (local_root / Path(relative_path)).resolve()
    if not local_path.is_relative_to(local_root) or not local_path.is_file():
        raise ValueError("File must exist inside payloads/ and not be a symlink escaping it")

    remote_path = (PurePosixPath(config["remote_dir"]) / relative_path).as_posix()
    parent = str(PurePosixPath(remote_path).parent)
    prepare = _run(host, "mkdir -p -- " + shlex.quote(parent), timeout_seconds=30)
    if prepare.get("exit_code") != 0:
        return {"host": host, "uploaded": False, "step": "mkdir", "result": prepare}

    argv = [_openssh("scp"), *_options(), str(local_path), f"{host}:{remote_path}"]
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    try:
        completed = subprocess.run(
            argv, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=120, check=False, creationflags=creationflags,
        )
    except subprocess.TimeoutExpired:
        return {"host": host, "uploaded": False, "error": "SCP timed out"}
    except OSError as exc:
        return {"host": host, "uploaded": False, "error": f"SCP could not start: {type(exc).__name__}"}
    return {
        "host": host, "uploaded": completed.returncode == 0,
        "remote_path": remote_path,
        "exit_code": completed.returncode,
        "stderr": _trim_and_redact(completed.stderr),
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")
