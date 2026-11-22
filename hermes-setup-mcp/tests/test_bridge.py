"""Exercise the bridge with fake SSH and MCP modules."""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest import TestCase
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
HOST = "hermes-server"


def load_bridge():
    class FakeMCP:
        def __init__(self, *args, **kwargs):
            pass

        def tool(self):
            return lambda function: function

    modules = {
        name: ModuleType(name)
        for name in ("keyring", "mcp", "mcp.server", "mcp.server.fastmcp")
    }
    modules["mcp.server.fastmcp"].FastMCP = FakeMCP
    spec = importlib.util.spec_from_file_location(
        "hermes_setup_mcp_test", ROOT / "hermes-setup-mcp.py"
    )
    bridge = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, modules):
        spec.loader.exec_module(bridge)
    bridge.CONFIG = ROOT / "hosts.example.json"
    return bridge


class BridgeTests(TestCase):
    def setUp(self):
        self.bridge = load_bridge()

    def test_sudo_secret_only_stdin(self):
        password = "fake-sudo-secret"
        with (
            patch.object(self.bridge, "_openssh", return_value="ssh"),
            patch.object(self.bridge, "_sudo_password", return_value=password),
            patch.object(self.bridge.subprocess, "run") as run,
        ):
            run.return_value.returncode = 0
            run.return_value.stdout = "ok"
            run.return_value.stderr = ""
            result = self.bridge.ssh_exec(HOST, "id && whoami", sudo=True)

        (argv,), kwargs = run.call_args
        self.assertEqual(result["exit_code"], 0)
        self.assertNotIn(password, str(argv))
        self.assertEqual(kwargs["input"], password + "\n")
        self.assertIn("exec </dev/null; id && whoami", argv[-1])
        self.assertIn("sudo -k -S", argv[-1])

    def test_unknown_host_rejected(self):
        with self.assertRaises(ValueError):
            self.bridge.ssh_exec("some-other-host", "id", sudo=True)

    def test_redaction(self):
        self.assertEqual(
            self.bridge._trim_and_redact("pass=abc123", "abc123"),
            "pass=[REDACTED]",
        )

    def test_upload_path_traversal_rejected(self):
        with self.assertRaises(ValueError):
            self.bridge.ssh_upload(HOST, "../credentials.py")
