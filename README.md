# Self-host Hermes Agent on Ubuntu Server

[Russian version](reandme-ru.md)

Set up a personal Hermes Agent from scratch on a dedicated home server or VPS. The setup covers a fresh Ubuntu Server, private HTTPS access to Hermes Webapp and Dashboard over Tailscale, and optional Telegram and Discord bots. Hermes runs under a dedicated system user. You can also publish knowledge base snapshots to a private GitHub repository.

Use [mise.toml](mise.toml) to install and verify the setup. The optional [hermes-setup-mcp](hermes-setup-mcp/README.md) lets a local agent run provisioning commands and transfer files over SSH.

## 1. Prepare the server and accounts

- Use a 64-bit Ubuntu Server with systemd, Bash, and Python 3.11 or later with `tomllib`. The tasks accept `x86_64` and `aarch64`. For a Raspberry Pi, use a model with at least 8 GB of RAM. Allow disk space for the Webapp build and Hermes data.
- Set up a non-root administrator with working `sudo`, OpenSSH on TCP port 22, and access to a local or provider console for recovery. Install your public SSH key when creating the server if possible.
- Check DNS, system time, and outbound access to the installers and the services you plan to use. Knowledge base publishing also requires outbound SSH to `github.com:22`.
- Prepare an account with a [Hermes model provider](https://hermes-agent.nousresearch.com/docs/integrations/providers), such as [Nous Portal](https://portal.nousresearch.com/manage-subscription), and a browser for sign-in. If you choose an external model provider, it processes the model requests.

For agent-assisted setup, use the included [local MCP server](hermes-setup-mcp/README.md) to speed up inspection, file uploads, and individual commands that need `sudo`. Enter the sudo password once when setting up the MCP server. During manual setup, `sudo` may prompt for it again across sessions or after its cache expires. Complete browser sign-ins, enter secrets, and run tasks that require an interactive terminal yourself.

### Tailscale

1. Install the [Tailscale client](https://tailscale.com/download) on each device you will use to access Hermes and sign in to the same tailnet. You will need permission to manage tags, grants, and Services, or help from a tailnet administrator.
2. In **DNS**, enable **MagicDNS** and **HTTPS Certificates**. Note the tailnet DNS suffix, such as `my-tailnet.ts.net`. Names on issued certificates may appear in Certificate Transparency logs. [Tailscale HTTPS](https://tailscale.com/docs/how-to/set-up-https-certificates)
3. In **Access controls**, add a tag owner to your existing `tagOwners` policy, for example `"tag:agent-server": ["autogroup:admin"]`. You will assign the tag to the host after it joins the tailnet.
4. In **Services**, define `hermes-dashboard` and `hermes-web`, each with a `tcp:443` endpoint. The tasks use these fixed names. In a shared tailnet, reserve both names for this instance because hosts advertising the same service can serve the same address. [Tailscale Services](https://tailscale.com/docs/features/tailscale-services)
5. Add a rule to your existing `grants` array for the intended user or group. Replace the example identity and check whether other tailnet rules also grant access. Keep Funnel disabled. [Tailscale grants](https://tailscale.com/docs/features/access-control/grants)

```json
{
  "src": ["operator@example.com"],
  "dst": ["svc:hermes-dashboard", "svc:hermes-web"],
  "ip": ["tcp:443"]
}
```

### Telegram and Discord

Set up either bot, both, or skip this step if you only need the Webapp.

- **Telegram.** Create a dedicated bot with `/newbot` in [@BotFather](https://t.me/BotFather). Save the token and find your numeric Telegram user ID. Once Gateway is running, open a direct chat with the bot and select **Start**. [Hermes Telegram setup](https://hermes-agent.nousresearch.com/docs/user-guide/messaging/telegram)
- **Discord.** Create an application in the [Developer Portal](https://discord.com/developers/applications), enable **Message Content Intent**, and save the bot token. Install the app in your Discord server with the `bot` and `applications.commands` scopes. For a private bot, follow the manual installation link instructions in the Hermes documentation. Give the bot **View Channel**, **Send Messages**, **Read Message History**, **Create Public Threads**, and **Send Messages in Threads** in the intended channels. In Discord, enable **Developer Mode** and copy your numeric **User ID** for the Hermes allowlist. Use the app's **Application ID** when installing it. [Hermes Discord setup](https://hermes-agent.nousresearch.com/docs/user-guide/messaging/discord)

## 2. Prepare the setup directory

On your workstation, replace `ADMIN` with the server administrator's username and `SERVER_IP` with the server address. Verify the SSH host-key fingerprint through the server console or your provider before connecting. If you need a key pair, create one with `ssh-keygen -t ed25519`.

```sh
ssh ADMIN@SERVER_IP
```

On the server, check `sudo`, identify the user and network, and create the setup directory.

```bash
sudo -v
whoami
ip -br -4 address
ip -4 route
timedatectl status
python3 -c 'import tomllib'
mkdir -p "$HOME/setup"
```

Install the following packages on the server if `curl`, CA certificates, or Python are missing. If the `tomllib` check still fails, use an image with Python 3.11 or later.

```bash
sudo apt-get update
sudo apt-get install -y curl ca-certificates python3
```

Install mise as the non-root administrator using the [official instructions](https://mise.jdx.dev/installing-mise.html). To install it in `~/.local/bin`, download and inspect the installer before running it.

```bash
cd "$HOME/setup"
curl -fsSLo install-mise.sh https://mise.run
less install-mise.sh
sh install-mise.sh
export PATH="$HOME/.local/bin:$PATH"
mise --version
```

On your workstation, check the SHA-256 of the original `mise.toml` before editing it.

| Platform | Command |
| --- | --- |
| Windows | `Get-FileHash ./mise.toml -Algorithm SHA256` |
| Linux | `sha256sum ./mise.toml` |
| macOS | `shasum -a 256 ./mise.toml` |

```text
10e89ecfe95115075a44f3c5ba5af387c24cb508d69135a892d7bb8466fc73cd
```

From the directory containing the file, send it to the server with the MCP tool or OpenSSH.

```sh
scp mise.toml ADMIN@SERVER_IP:setup/mise.toml
```

On the server, open `~/setup/mise.toml` and review the `[env]` settings.

| Setting | Value |
| --- | --- |
| `ADMIN_USER` | The non-root administrator shown by `whoami`. |
| `LAN_IF`, `LAN_NET` | For LAN-only SSH, use the actual interface and its IPv4 prefix from `ip`, for example `eth0` and `192.168.1.0/24`. |
| `TAILSCALE_TAG` | The tag you prepared in Tailscale. |
| `HERMES_USER`, `WEB_PORT` | Keep `hermes` and `9120`, which the tasks expect. |

Run subsequent mise commands from `~/setup` as `ADMIN_USER`. In a new SSH session, add `~/.local/bin` to `PATH` again if you installed mise there. Review the configuration before granting it trust. [mise trust](https://mise.jdx.dev/cli/trust.html)

```bash
cd "$HOME/setup"
less mise.toml
mise trust ./mise.toml
mise run validate
mise run preflight
```

`validate` checks TOML, Bash syntax, and task dry runs. `preflight` checks the OS, user, Python, and sudo access and reports network, memory, and disk information. Resolve any error before continuing.

## 3. Configure SSH, the firewall, and the Hermes user

1. Run `mise run packages` to install system dependencies and enable automatic security updates.
2. If your key is missing from the server, run `mise run ssh-key` and paste the contents of the public `.pub` file. Keep the existing SSH session open. On your workstation, open a separate key-only SSH session using the path to your private key.

   ```sh
   ssh -i "PATH_TO_PRIVATE_KEY" -o ControlPath=none -o IdentitiesOnly=yes -o PreferredAuthentications=publickey -o PasswordAuthentication=no -o KbdInteractiveAuthentication=no ADMIN@SERVER_IP
   ```

3. Verify that `ssh.service` is active and the key works. Run `mise run ssh-harden`. The task asks you to confirm the separate key-only login, then disables password authentication and root login over SSH. Verify key-only access again with a new connection.
4. **Use the LAN firewall tasks only for direct SSH access over a private IPv4 LAN on TCP port 22.** Run `mise run firewall-stage` from that connection. Within five minutes, open a fresh SSH connection with the same settings and run `mise run firewall-commit` from that new session, outside `tmux`, `su`, and `sudo`. The task checks for a directly connected RFC 1918 network and a fresh logind session. If the new connection fails, keep the original open and wait for rollback or run `mise run firewall-rollback` there. For a VPS administered over public or routed SSH, skip both tasks and set the SSH access rules in your provider's firewall to match your management network.
5. Run `mise run user` to create a dedicated `hermes` user without sudo privileges and enable its systemd user manager with lingering.

## 4. Install Hermes, connect a model, and start Gateway

| Command | What to expect |
| --- | --- |
| `mise run hermes-install` | Installs Hermes under the `hermes` account and reports the version. It retains the existing installation if the CLI is already present. |
| `HERMES_SETUP_SELECT_MODEL=1 mise run hermes-model` | Starts provider and model selection. Sign in with your provider and wait for the model to return `OK`. |
| `mise run telegram` | Optional. Prompts for the bot token and one allowed numeric user ID. Leave the token blank to keep an existing one. |
| `mise run discord-setup` | Optional. Prompts for the bot token and allowed user ID. Start a conversation by mentioning the bot in a channel and continue in its thread. |
| `mise run gateway` | Installs and enables the Gateway user service. If applying changes requires a restart, the task prompts for confirmation. |
| `mise run discord-status` | If you configured Discord, checks the Gateway service. Verify the bot's actual reply in Discord. |

If the setup wizard displays a URL and code, complete the sign-in in your browser. If OAuth uses a callback on the server's `localhost`, open a separate SSH tunnel from your workstation. Replace both occurrences of `PORT` with the port specified by the provider. Keep the tunnel open until CLI sign-in finishes. [OAuth over SSH](https://hermes-agent.nousresearch.com/docs/guides/oauth-over-ssh)

```sh
ssh -N -o ExitOnForwardFailure=yes -L PORT:127.0.0.1:PORT ADMIN@SERVER_IP
```

Run `mise run hermes-model` again to check the existing model configuration without reopening the setup wizard.

## 5. Open Webapp and Dashboard from your tailnet

| Interface | Service and address |
| --- | --- |
| Hermes Webapp for chatting with the agent | Gateway at `127.0.0.1:9120`, published at `https://hermes-web.TAILNET.ts.net` |
| Hermes Dashboard for configuration and diagnostics | Separate `hermes-dashboard.service` at `127.0.0.1:9119`, published at `https://hermes-dashboard.TAILNET.ts.net` |

Replace `TAILNET.ts.net` with your tailnet's DNS suffix. Browser access requires a connection to the tailnet and a separate local Basic Auth sign-in. Model provider sign-in is also separate.

1. Run `mise run tailscale-install`, then `mise run tailscale-login`. Finish sign-in in the browser, verify the tailnet, and assign the prepared tag to the host in **Machines**.
2. If the Webapp bundle is missing, run `mise run webapp-build`. The build may download dependencies.
3. Check that Gateway is running. Run `mise run webapp` in an interactive session. It configures the address and Basic Auth, then restarts Gateway if its configuration changes. Save the local sign-in credentials if the task issues them.
4. Run `mise run dashboard-install` and `mise run dashboard-status`. Dashboard uses the same local sign-in credentials.
5. Run `mise run services-configure`. If host approvals are manual, open **Services**, select each service, and approve the host under **Service hosts**. Run `mise run services-status` and open both addresses from a device in the tailnet. [Tailscale Services](https://tailscale.com/docs/features/tailscale-services)

See the Hermes documentation for [Webapp configuration](https://hermes-agent.nousresearch.com/docs/user-guide/configuration) and [Dashboard sign-in](https://hermes-agent.nousresearch.com/docs/user-guide/features/web-dashboard).

## 6. Optionally publish knowledge base snapshots

Create a **separate, empty private GitHub repository**. Leave the initial README, .gitignore, and license options unchecked. The agent writes to `/srv/knowledge`. A dedicated system user, `kb-backup`, pushes prepared snapshots to `main`. Publishing is one-way, from the server to GitHub.

1. Run `mise run kb-storage`. Point any Hermes sessions that need access to `/srv/knowledge`.
2. Run `mise run kb-git-key`. Add the displayed public key under **Settings → Deploy keys → Add deploy key** and enable **Allow write access**. [GitHub deploy keys](https://docs.github.com/en/authentication/connecting-to-github-with-ssh/managing-deploy-keys)
3. Check repository visibility and review the knowledge base contents before running `mise run kb-git-setup`. Enter an SSH URL such as `git@github.com:OWNER/REPO.git`. The task **pushes the first snapshot immediately**, then enables a five-minute timer. Filters check file names and types. Markdown is pushed with its full contents, and deleted files can remain in Git history.
4. Run `mise run kb-verify` to check access permissions, the timer, and whether the local and remote branches match.

## 7. Verify your setup

| Check | Expected result |
| --- | --- |
| SSH | A fresh key-only SSH connection succeeds. Password authentication is disabled. If you enabled the LAN firewall, verify that its rules persist across a reboot. |
| Model and Gateway | `mise run hermes-model` gets the expected reply. Gateway is active and enabled at startup. |
| Webapp and Dashboard | `mise run services-status` passes. Both addresses prompt for sign-in and accept the local credentials. Send a message in Webapp and open Gateway status in Dashboard. Check that the addresses are unreachable off the tailnet and that a test account without a matching grant is denied access, if such an account is available. |
| Bots | If configured, Telegram replies in a direct chat and Discord replies to a mention and continues in the thread. A request from a user outside the allowlist does not invoke the agent. |
| Knowledge base | If enabled, `mise run kb-verify` passes and the private `main` branch receives an approved change. |
| Reboot | If you ran `mise run reboot`, repeat the checks for the enabled components. |

## Maintenance

| Command | Effect |
| --- | --- |
| `mise run firewall-rollback` | Removes the managed LAN SSH restriction and its startup configuration after confirmation. Run from a working SSH session or console. |
| `HERMES_SETUP_RESTART_GATEWAY=1 mise run gateway` | Requests a Gateway restart after confirmation. Let active work finish first. |
| `mise run webapp-on` / `mise run webapp-off` | Enables or disables Webapp through the Gateway configuration and restarts Gateway if it changes. |
| `mise run dashboard-on` / `mise run dashboard-off` | Controls Dashboard and its startup behavior independently. |
| `HERMES_SETUP_ROTATE_WEBAPP_PASSWORD=1 mise run webapp` | Rotates the password and signing secret. Restart Dashboard using `dashboard-off` and `dashboard-on`, then verify both sign-ins. |
| `mise run services-off` | Removes the two HTTPS routes. Restore them with `mise run services-configure` and check host approval. |
| `mise run kb-backup-now` / `mise run kb-pause` | Publishes a snapshot outside the schedule or disables scheduled publishing. Resume with `mise run kb-git-setup`. |
| `mise run otel-install` / `mise run otel-status` | Installs the `hermes_otel` plugin in a disabled state or shows its status. Review the telemetry destination before enabling it. [Hermes OpenTelemetry plugin](https://hermes-agent.nousresearch.com/marketplace/hermes_otel) |
| `mise run reboot` | Reboots the server after confirmation. Verify access and finish any staged firewall change first. |
