# hermes-setup-mcp

Run a local MCP server to help an agent provision a dedicated Ubuntu Server over SSH. The workstation setup was checked on native Windows with Windows OpenSSH, `ssh-agent`, and Windows Credential Manager. On Linux and macOS, SSH requires a working OpenSSH client and access to its `ssh-agent`. Privileged commands also need a platform-specific credential store integration. The included sudo credential helper requires Windows.

The target can be a physical server, a VM, a VPS, or a Raspberry Pi. For a Raspberry Pi running the full Hermes setup, use a 64-bit Ubuntu Server image and a model with at least 8 GB of RAM.

The local agent can inspect configured hosts, upload files, and run individual commands with or without sudo. A call with `sudo=true` can run arbitrary root commands on the configured target. Code running under the same Windows user can access the same stored credential, so use a trusted local MCP client and restrict the SSH aliases to servers you administer.

## 1. Install the local dependencies

On Windows, open a terminal in this directory. Use native Windows Python 3.11 or later under the Windows account that will run your MCP client.

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

The MCP client starts the Python process on demand over standard input and output. The server needs no separate daemon.

## 2. Configure the SSH alias and upload directory

Add an entry to your workstation's `~/.ssh/config`. Replace the hostname, Linux administrator, and key path with your own values.

```sshconfig
Host hermes-server
    HostName server.example.net
    User admin
    IdentityFile ~/.ssh/id_ed25519
    IdentitiesOnly yes
    StrictHostKeyChecking yes
    ForwardAgent no
```

Verify the server's host-key fingerprint through its console or provider and add the verified key to your `known_hosts`. The MCP server requires a pretrusted host key and noninteractive key authentication.

For a passphrase-protected key, load it into the Windows OpenSSH agent. If the service is disabled or stopped, enable and start it from an elevated terminal. [Windows OpenSSH key management](https://learn.microsoft.com/en-us/windows-server/administration/openssh/openssh_keymanagement)

```powershell
Get-Service ssh-agent
Set-Service ssh-agent -StartupType Manual
Start-Service ssh-agent
```

In your own terminal, use the Windows OpenSSH binaries and verify that a noninteractive login works. Adjust the key path if needed.

```powershell
& "$env:WINDIR/System32/OpenSSH/ssh-add.exe" "$env:USERPROFILE/.ssh/id_ed25519"
& "$env:WINDIR/System32/OpenSSH/ssh-add.exe" -l
& "$env:WINDIR/System32/OpenSSH/ssh.exe" -o BatchMode=yes hermes-server "hostname && id"
```

Copy [hosts.example.json](hosts.example.json) to `hosts.json` in this directory. The JSON key must match the SSH alias. Set `remote_dir` to an absolute path writable by the ordinary SSH user, such as `/home/admin/setup`. Use that user's actual home directory and the `setup` location from the [server guide](../README.md).

## 3. Store the remote sudo password

Run the credential helper from your own terminal. It prompts for the Ubuntu administrator's sudo password with hidden input and stores it in Windows Credential Manager for this Windows account. The SSH key passphrase is a separate credential.

```powershell
.\.venv\Scripts\python.exe credentials.py set hermes-server
.\.venv\Scripts\python.exe credentials.py status hermes-server
```

The credential is stored under service `hermes-setup-mcp-sudo` and the SSH alias. To remove it when you are done, run the same helper with `delete hermes-server`.

## 4. Register the MCP server and skill

Register a local **stdio** server named `hermes-setup-mcp` in your MCP client. Use the absolute path to `.venv/Scripts/python.exe` as the command and the absolute path to [hermes-setup-mcp.py](hermes-setup-mcp.py) as its single argument. [mcp-config.example.json](mcp-config.example.json) shows the common JSON shape. Replace both paths and adapt the settings to your client's configuration format.

Restart or reload the client if needed. Check that the tool list contains `list_hosts`, `ssh_exec`, and `ssh_upload`. If your client supports agent skills, open the repository root and select the included [hermes-setup skill](../.agents/skills/hermes-setup/SKILL.md). If it uses a different skill discovery path, consult the client's instructions for installing that skill.

## 5. Use the tools with the server guide

Place your copy of `mise.toml` in this directory's `payloads/` folder. Use the [server guide](../README.md) to choose the correct parameters and task order. Upload only files needed for provisioning. Keep secrets in the credential store or enter them yourself in an interactive session.

| Tool | Example arguments |
| --- | --- |
| `list_hosts` | `{}` |
| `ssh_exec` | `{"host":"hermes-server","command":"cat /etc/os-release; id"}` |
| `ssh_upload` | `{"host":"hermes-server","relative_path":"mise.toml"}` |
| `ssh_exec` | `{"host":"hermes-server","command":"systemctl is-active ssh","sudo":false}` |
| `ssh_exec` | `{"host":"hermes-server","command":"id -u","sudo":true}` |

The last command is an optional sudo check. A successful result has `exit_code: 0` and prints `0`. Follow the main guide for the actual installation sequence.

Example prompt for an agent:

> Use the hermes-setup skill and the local hermes-setup-mcp tools to prepare hermes-server with this repository's README and mise.toml. Inspect the target first. Use the tools for inspection, uploads, and individual noninteractive commands. Tell me which steps require my terminal or browser and wait for me at those checkpoints. Verify the enabled services at the end.

## How sudo and interactive steps work

- For a privileged call, the bridge supplies the stored password to `sudo -S` over SSH stdin. The root command starts with stdin closed. The password stays out of command-line arguments and environment variables. Returned output is length-limited, and literal copies of the stored password are redacted.
- The bridge uses SSH without a terminal. Run mise as the ordinary administrator in an interactive SSH session when a task needs input, a terminal, or a sudo prompt inside the task. Keep SSH hardening, firewall confirmation, OAuth, and token entry in the operator's session. Use the MCP tool for individual privileged commands that can run without interaction.
- If the target enforces a sudo TTY requirement, the MCP sudo call fails. If SSH times out, check the remote state before retrying because the command may have kept running.

## Local tests

The tests simulate SSH and credentials. From this directory, run them with Python:

```text
python -m unittest discover -s tests -v
```
