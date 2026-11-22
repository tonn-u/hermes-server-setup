---
name: hermes-setup
description: Provision and verify a dedicated Ubuntu host for Hermes Agent using the local hermes-setup-mcp server, the repository README, and mise.toml.
---

# Set up a dedicated Hermes server

1. Read the repository README and `mise.toml`. Confirm the requested target with `list_hosts`. Ask the operator to configure the alias if it is absent.
2. Inspect the target with `ssh_exec` as the ordinary SSH user. Check the OS, identity, architecture, free space, network, and whether mise is available. Identify which components the operator wants to enable.
3. Confirm the administrator, LAN settings, and Tailscale tag before staging `mise.toml`. Put the customized file in the MCP server's local `payloads/` directory and upload it with `ssh_upload`. Paths sent to this tool are relative to `payloads/`. The remote destination comes from `hosts.json`.
4. Follow the README in order. Use `ssh_exec` with `sudo=false` for ordinary commands and `sudo=true` for discrete root operations that need elevated permissions. Read the corresponding task before executing a prerequisite separately.
5. Hand off interactive steps to the operator's SSH session, including secret entry, OAuth, SSH and firewall confirmation, and mise tasks that need a terminal or nested sudo. Keep the original SSH connection open when the README calls for a fresh connection. Run mise as the configured ordinary administrator.
6. Check exit codes and the state of each enabled service. After a timeout, inspect remote state before retrying. Ask the operator to verify browser sign-in and bot replies and report which checks passed.

Keep passwords, tokens, and private keys out of conversation, commands, logs, and uploaded files. The operator enrolls the sudo password directly in the local credential store. Keep SSH host-key validation enabled. Use only the intended SSH alias and operator-approved steps.
