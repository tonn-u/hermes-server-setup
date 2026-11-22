# Hermes Agent на выделенном Ubuntu Server

[English](README.md)

Настройка личного Hermes Agent с нуля на выделенном сервере (локальный или VPS). Ранбук для чистого linux (Ubuntu Server), приватный доступ к Hermes Webapp и Dashboard по HTTPS через Tailscale, а также настройка Telegram и Discord на выбор. Hermes работает под отдельным системным пользователем. Публикацию снимков базы знаний в приватный GitHub можно включить отдельно.

[mise.toml](mise.toml) содержит задачи для установки и проверки. [hermes-setup-mcp](hermes-setup-mcp/README.md) помогает выполнять команды и переносить файлы через агента.

## 1. Подготовьте сервер и доступы

- Сервер с 64-битным Ubuntu Server, systemd, Bash и Python 3.11+ с `tomllib`. Поддерживаемые архитектуры — `x86_64` и `aarch64`. Для Raspberry Pi рекомендуется модель с 8 ГБ ОЗУ или больше. Оставьте место под сборку Webapp и данные Hermes.
- Обычный пользователь с рабочим `sudo`, OpenSSH на TCP 22 и резервный доступ через локальную консоль или консоль провайдера. По возможности добавьте публичный SSH-ключ при создании сервера.
- Рабочие DNS и системное время, исходящий доступ к источникам установки и выбранным сервисам. Для снимков базы знаний нужен исходящий SSH к `github.com:22`.
- Аккаунт у [провайдера модели Hermes](https://hermes-agent.nousresearch.com/docs/integrations/providers), например [Nous Portal](https://portal.nousresearch.com/manage-subscription), и браузер для входа. При использовании внешнего провайдера запросы модели обрабатываются у него.

Для настройки через агента рекомендуется прилагаемый [локальный MCP](hermes-setup-mcp/README.md). Он ускоряет проверку сервера, загрузку файлов и отдельные команды с `sudo`. Пароль для этих команд вводится один раз при настройке MCP (используется credentials store). При ручной установке `sudo` может запрашивать пароль повторно. Вход в аккаунты, ввод токенов и задачи, которым нужен интерактивный терминал, выполняйте сами.

### Tailscale

1. Установите [клиент Tailscale](https://tailscale.com/download) на устройства, с которых будете открывать Hermes, и войдите в нужный tailnet. Для дальнейших настроек понадобятся права управления тегами, grants и Services или помощь администратора.
2. В **DNS** включите **MagicDNS** и **HTTPS Certificates**. Запишите DNS-суффикс tailnet, например `my-tailnet.ts.net`. Имена, для которых выдаются сертификаты, могут появляться в журналах Certificate Transparency. [Документация HTTPS](https://tailscale.com/docs/how-to/set-up-https-certificates)
3. В **Access controls** добавьте владельца тега сервера в существующий `tagOwners`, например `"tag:agent-server": ["autogroup:admin"]`. Позже назначьте этот тег узлу.
4. В **Services** создайте `hermes-dashboard` и `hermes-web`, оба с endpoint `tcp:443`. Эти имена фиксированы в задачах. В общем tailnet выделите их этому экземпляру Hermes, поскольку хосты с одним именем сервиса могут обслуживать один адрес. [Tailscale Services](https://tailscale.com/docs/features/tailscale-services)
5. Добавьте в действующий массив `grants` правило для нужного пользователя или группы. Замените адрес в примере своим и проверьте доступ по остальным правилам tailnet. Оставьте Funnel выключенным. [Tailscale grants](https://tailscale.com/docs/features/access-control/grants)

```json
{
  "src": ["operator@example.com"],
  "dst": ["svc:hermes-dashboard", "svc:hermes-web"],
  "ip": ["tcp:443"]
}
```

### Telegram и Discord

Подготовьте один из каналов, оба или пропустите их, если достаточно Webapp.

- **Telegram.** Создайте отдельного бота через [@BotFather](https://t.me/BotFather) командой `/newbot`. Сохраните токен и узнайте числовой User ID своего аккаунта. После запуска Gateway откройте личный чат с ботом и нажмите **Start**. [Telegram в Hermes](https://hermes-agent.nousresearch.com/docs/user-guide/messaging/telegram)
- **Discord.** Создайте приложение в [Developer Portal](https://discord.com/developers/applications), включите **Message Content Intent** и сохраните токен бота. Установите приложение в свой Discord-сервер с разрешениями `bot` и `applications.commands`. Для приватного бота используйте ручную ссылку установки из документации Hermes. В выбранных каналах выдайте боту **View Channel**, **Send Messages**, **Read Message History**, **Create Public Threads** и **Send Messages in Threads**. В клиенте Discord включите **Developer Mode** и скопируйте свой числовой **User ID** для списка доступа Hermes. Для установки используется **Application ID** приложения. [Discord в Hermes](https://hermes-agent.nousresearch.com/docs/user-guide/messaging/discord)

## 2. Подготовьте каталог setup

На рабочем компьютере подставьте имя администратора вместо `ADMIN` и адрес сервера вместо `SERVER_IP`. Проверьте отпечаток ключа сервера через его консоль или у провайдера, затем подключитесь. Если SSH-ключа ещё нет, создайте его командой `ssh-keygen -t ed25519`.

```sh
ssh ADMIN@SERVER_IP
```

На сервере проверьте `sudo`, узнайте пользователя и сеть, затем создайте каталог.

```bash
sudo -v
whoami
ip -br -4 address
ip -4 route
timedatectl status
python3 -c 'import tomllib'
mkdir -p "$HOME/setup"
```

Если `curl`, корневых сертификатов или Python ещё нет, установите их на сервере. Если импорт `tomllib` всё ещё завершается ошибкой, используйте образ с Python 3.11 или новее.

```bash
sudo apt-get update
sudo apt-get install -y curl ca-certificates python3
```

Установите mise под обычным администратором по [официальной инструкции](https://mise.jdx.dev/installing-mise.html). Для установки в `~/.local/bin` можно скачать и просмотреть скрипт перед запуском.

```bash
cd "$HOME/setup"
curl -fsSLo install-mise.sh https://mise.run
less install-mise.sh
sh install-mise.sh
export PATH="$HOME/.local/bin:$PATH"
mise --version
```

На рабочем компьютере проверьте SHA-256 исходного `mise.toml` до редактирования.

| Платформа | Команда |
| --- | --- |
| Windows | `Get-FileHash ./mise.toml -Algorithm SHA256` |
| Linux | `sha256sum ./mise.toml` |
| macOS | `shasum -a 256 ./mise.toml` |

```text
10e89ecfe95115075a44f3c5ba5af387c24cb508d69135a892d7bb8466fc73cd
```

Из каталога с файлом загрузите его на сервер через MCP или OpenSSH.

```sh
scp mise.toml ADMIN@SERVER_IP:setup/mise.toml
```

На сервере откройте `~/setup/mise.toml` и проверьте параметры в `[env]`.

| Параметр | Что указать |
| --- | --- |
| `ADMIN_USER` | Имя обычного администратора из `whoami`. |
| `LAN_IF`, `LAN_NET` | Для ограничения SSH из LAN — интерфейс и его фактический IPv4-префикс из `ip`. Например, `eth0` и `192.168.1.0/24`. |
| `TAILSCALE_TAG` | Тег, подготовленный в Tailscale. |
| `HERMES_USER`, `WEB_PORT` | Оставьте `hermes` и `9120`. На эти значения рассчитаны задачи. |

Дальнейшие команды `mise` запускайте из `~/setup` под `ADMIN_USER`. В новом сеансе снова добавьте `~/.local/bin` в `PATH`, если mise установлен туда. Ознакомьтесь с конфигурацией перед тем, как доверять ей. [mise trust](https://mise.jdx.dev/cli/trust.html)

```bash
cd "$HOME/setup"
less mise.toml
mise trust ./mise.toml
mise run validate
mise run preflight
```

`validate` проверяет TOML, синтаксис Bash и сухой прогон задач. `preflight` проверяет ОС, пользователя, Python и `sudo`, выводит сведения о сети, памяти и диске. При ошибке остановитесь и устраните её перед следующим шагом.

## 3. Настройте SSH, firewall и пользователя Hermes

1. Запустите `mise run packages`. Задача ставит системные зависимости и включает автоматические обновления безопасности.
2. Если ключ ещё не установлен, запустите `mise run ssh-key` и вставьте содержимое публичного файла `.pub`. Оставьте текущий SSH-сеанс открытым. На рабочем компьютере откройте отдельный сеанс по ключу. Подставьте свой путь к приватному ключу.

   ```sh
   ssh -i "PATH_TO_PRIVATE_KEY" -o ControlPath=none -o IdentitiesOnly=yes -o PreferredAuthentications=publickey -o PasswordAuthentication=no -o KbdInteractiveAuthentication=no ADMIN@SERVER_IP
   ```

3. Убедитесь, что `ssh.service` активен и вход по ключу работает. Запустите `mise run ssh-harden`: задача требует отдельной проверки входа, выключает парольную аутентификацию и SSH-вход для root. Снова проверьте вход по ключу отдельным соединением.
4. **Только при прямом доступе из частной IPv4 LAN на TCP 22.** Запустите `mise run firewall-stage` из прямого SSH-сеанса. В течение пяти минут подключитесь заново с теми же параметрами и выполните `mise run firewall-commit` из нового сеанса, вне `tmux`, `su` и `sudo`. Скрипт проверяет прямую сеть RFC 1918 и новый сеанс в logind. При проблемах оставьте исходный сеанс открытым и дождитесь отката или запустите в нём `mise run firewall-rollback`. На VPS с публичным или маршрутизируемым административным SSH пропустите обе задачи и настройте правила доступа к SSH в firewall провайдера под свою схему доступа.
5. Запустите `mise run user`. Задача создаёт пользователя `hermes` без sudo и включает его пользовательский systemd с linger.

## 4. Установите Hermes, подключите модель и запустите Gateway

| Команда | Что ожидать |
| --- | --- |
| `mise run hermes-install` | Устанавливает Hermes под пользователем `hermes` и выводит версию. При наличии CLI сохраняет текущую установку. |
| `HERMES_SETUP_SELECT_MODEL=1 mise run hermes-model` | Открывает выбор провайдера и модели. Пройдите вход у выбранного провайдера и дождитесь контрольного ответа `OK`. |
| `mise run telegram` | По желанию. Запрашивает токен бота и один разрешённый числовой User ID. Пустой ввод сохраняет текущий токен. |
| `mise run discord-setup` | По желанию. Запрашивает токен и разрешённый User ID. В канале диалог начинается с упоминания бота и продолжается в треде. |
| `mise run gateway` | Устанавливает и включает пользовательский Gateway. Если нужен перезапуск для применения настроек, задача попросит подтверждение. |
| `mise run discord-status` | Если включён Discord, проверяет службу Gateway. Ответ бота проверяется в Discord. |

Если мастер выдаст URL и код, завершите вход в браузере. Для OAuth с callback на `localhost` сервера откройте отдельное SSH-подключение с пробросом порта с рабочего компьютера. Замените оба `PORT` портом из инструкции провайдера. Держите туннель открытым до завершения входа в CLI. [OAuth через SSH](https://hermes-agent.nousresearch.com/docs/guides/oauth-over-ssh)

```sh
ssh -N -o ExitOnForwardFailure=yes -L PORT:127.0.0.1:PORT ADMIN@SERVER_IP
```

Для повторной проверки текущей конфигурации используйте `mise run hermes-model`, который проверяет ответ модели без открытия мастера.

## 5. Откройте Webapp и Dashboard в tailnet

| Интерфейс | Сервис и адрес |
| --- | --- |
| Hermes Webapp для работы с агентом | Gateway, `127.0.0.1:9120`, `https://hermes-web.TAILNET.ts.net` |
| Hermes Dashboard для настройки и диагностики | Отдельная служба `hermes-dashboard.service`, `127.0.0.1:9119`, `https://hermes-dashboard.TAILNET.ts.net` |

Замените `TAILNET.ts.net` DNS-суффиксом своего tailnet. Доступ из браузера требует входа в tailnet и отдельного локального логина Basic Auth. Вход у провайдера модели настраивается отдельно.

1. Запустите `mise run tailscale-install`, затем `mise run tailscale-login`. Подтвердите вход в браузере, проверьте tailnet и назначьте хосту подготовленный тег в **Machines**.
2. При отсутствии готового Webapp bundle запустите `mise run webapp-build`. Задача может скачать зависимости.
3. Проверьте, что Gateway запущен, затем выполните `mise run webapp` в интерактивном сеансе. Задача настраивает адрес и Basic Auth и при изменении конфигурации перезапускает Gateway. Сохраните выданные локальные данные для входа.
4. Запустите `mise run dashboard-install` и `mise run dashboard-status`. Dashboard использует те же локальные данные для входа.
5. Запустите `mise run services-configure`. При ручном одобрении откройте **Services → нужный сервис → Service hosts** и одобрите хост для обоих сервисов. Выполните `mise run services-status`, затем откройте оба адреса с устройства в tailnet. [Tailscale Services](https://tailscale.com/docs/features/tailscale-services)

В документации Hermes описаны [параметры Webapp](https://hermes-agent.nousresearch.com/docs/user-guide/configuration) и [вход в Dashboard](https://hermes-agent.nousresearch.com/docs/user-guide/features/web-dashboard).

## 6. По желанию публикуйте снимки базы знаний

Создайте **отдельный пустой приватный репозиторий** GitHub. При создании оставьте начальные README, .gitignore и лицензию выключенными. Агент пишет в `/srv/knowledge`. Отдельный системный пользователь `kb-backup` отправляет подготовленные снимки в ветку `main`. Изменения из GitHub обратно не подтягиваются.

1. Выполните `mise run kb-storage` и укажите путь `/srv/knowledge` сессиям Hermes, которым нужен доступ к базе.
2. Выполните `mise run kb-git-key`. Добавьте выведенный публичный ключ в **Settings → Deploy keys → Add deploy key** с флагом **Allow write access**. [GitHub deploy keys](https://docs.github.com/en/authentication/connecting-to-github-with-ssh/managing-deploy-keys)
3. Проверьте видимость репозитория и содержимое базы, затем выполните `mise run kb-git-setup`. Укажите SSH URL вида `git@github.com:OWNER/REPO.git`. Задача **сразу отправляет первый снимок**, затем включает таймер с интервалом пять минут. Фильтры проверяют имена и типы файлов. Содержимое Markdown отправляется целиком, а удалённые файлы могут остаться в истории коммитов.
4. Выполните `mise run kb-verify`. Задача проверяет права, таймер и совпадение локальной и удалённой веток.

## 7. Проверьте установку

| Проверка | Критерий готовности |
| --- | --- |
| SSH | Новый вход по ключу работает. Парольный SSH-вход выключен. При настройке LAN firewall подтвердите, что правила сохраняются при перезапуске. |
| Модель и Gateway | `mise run hermes-model` получает контрольный ответ. Gateway активен и включён на старте. |
| Webapp и Dashboard | `mise run services-status` проходит. Оба адреса в tailnet предлагают вход и принимают локальные данные. Отправьте сообщение в Webapp и откройте состояние Gateway в Dashboard. Проверьте недоступность без Tailscale и, при наличии тестовой учётной записи, без разрешающего grant. |
| Боты | Если настроены, Telegram отвечает в личном чате, а Discord отвечает на упоминание и продолжает в треде. Запрос от пользователя вне списка доступа не запускает агента. |
| База знаний | Если включена, `mise run kb-verify` проходит и приватный `main` обновляется после разрешённого изменения. |
| Перезапуск | Если выполняли `mise run reboot`, повторите проверки для включённых компонентов. |

## Обслуживание

| Команда | Действие |
| --- | --- |
| `mise run firewall-rollback` | Снимает ограничение SSH из LAN и его автозагрузку после подтверждения. Запускайте из рабочего SSH-сеанса или консоли. |
| `HERMES_SETUP_RESTART_GATEWAY=1 mise run gateway` | Явно перезапускает Gateway после подтверждения. Сначала завершите активные задачи. |
| `mise run webapp-on` / `mise run webapp-off` | Управляет Webapp через конфигурацию Gateway и перезапускает Gateway при изменениях. |
| `mise run dashboard-on` / `mise run dashboard-off` | Отдельно управляет Dashboard и его автозагрузкой. |
| `HERMES_SETUP_ROTATE_WEBAPP_PASSWORD=1 mise run webapp` | Меняет пароль и signing secret. Затем перезапустите Dashboard через `dashboard-off` и `dashboard-on` и проверьте оба входа. |
| `mise run services-off` | Удаляет два маршрута HTTPS. Для восстановления используйте `mise run services-configure` и проверьте одобрение хоста. |
| `mise run kb-backup-now` / `mise run kb-pause` | Отправляет снимок вне расписания или выключает расписание. Для возобновления используйте `mise run kb-git-setup`. |
| `mise run otel-install` / `mise run otel-status` | Устанавливает выключенный плагин `hermes_otel` или показывает его состояние. Перед включением проверьте назначение телеметрии. [OpenTelemetry для Hermes](https://hermes-agent.nousresearch.com/marketplace/hermes_otel) |
| `mise run reboot` | Перезагружает ОС после подтверждения. Проверьте доступ и завершите стадию firewall перед перезапуском. |
