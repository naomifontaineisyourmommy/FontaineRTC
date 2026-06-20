# API FontaineRTC

Три поверхности API. Шифрование/протокол — см. [PROTOCOL.md](PROTOCOL.md).

---

## 1. Внешний зашифрованный API админки — `POST /api/v1`

Публичный API для внешних интеграций (бот, биллинг). Тело зашифровано `api_key`
админки (Hash-CTR + HMAC, поле `ts`, допуск ±60с). **Единственное действие:**

`{"action": "list", "ts": <unix>}` →
```json
{
  "users": [
    {
      "client_id": "…", "uri": "olcrtc://…",
      "status": "active|inactive",
      "peers_count": 2, "peers_devices": ["hwid1", …],
      "server_name": "DE-01", "server_country": "Germany", "group_id": 1
    }
  ],
  "wdtt": [
    {
      "password": "…", "status": "active|bound|expired|deactivated",
      "expires_at": 1784406215, "down_bytes": 0, "up_bytes": 0,
      "device_id": "", "device_ip": "",
      "vk_hash": "…", "uri": "wdtt://…",
      "server_name": "DE-01", "server_country": "Germany", "group_id": 1
    }
  ]
}
```
`status=active` (для `users`), если инстанс запущен **и** URI готова. Всё
агрегируется по всем нодам. `peers_devices` — HWID подключённых OlcRTC-клиентов.

`wdtt` — пользователи (пароли) WDTT по всем нодам. `vk_hash` и `uri` присутствуют
только если при создании был указан VK-хеш; тогда `uri` — готовая ссылка
`wdtt://IP:DTLS:WG:TUN:ПАРОЛЬ:VK_HASH`. Статусы WDTT: `active` (не привязан),
`bound` (привязан к устройству), `expired`, `deactivated`.

> Это весь внешний API админки — намеренно минимальный (как в оригинале), только чтение.

---

## 2. Внешний зашифрованный API ноды — `POST /api/v1`

Им пользуется админка. Шифрование — `api_key` ноды. Действия:

| Действие | Назначение |
|:--|:--|
| `list` | инстансы (полный конфиг inline) + `server` (CPU/RAM) + `jitsi_domains` + блок `wdtt` |
| `get_user` / `set_user` | прочитать / изменить инстанс |
| `create_user` | создать (по умолчанию jitsi+datachannel) |
| `start_user` / `stop_user` / `delete_user` | управление одним |
| `start_all` / `stop_all` / `restart_all` | массовые |
| `set_jitsi_domains` | список доменов |
| `set_push_target` | URL админки для push (`""` = выкл) |
| `update_panel` | обновление панели (FontaineRTC + olcrtc + WDTT, гейтится версией) |
| `wdtt_status` | статус WDTT: `{installed, active, main_password, version, users}` |
| `wdtt_list` | `{users: [...]}` — пользователи WDTT (см. поля выше) |
| `wdtt_add` | создать пароль: `{days, password?, host?, vk_hash?}` → `{password, host, uri?}` |
| `wdtt_del` | удалить пароль: `{password}` |
| `wdtt_toggle` | вкл/выкл пароль: `{password, deactivated}` |

> Блок `wdtt` в `list` = `{installed, active, main_password, version, users:[…]}`;
> поля пользователя те же, что в массиве `wdtt` внешнего API админки (выше).

---

## 3. Внутренний web-API (для SPA, авторизация по `X-Token`)

Логин: `POST /api/login {password}` → `{token}` (stateless, переживает рестарт).
Открытые (без токена): `GET /healthz`, `GET /api/updating`, `GET /api/version`,
а у админки ещё `POST /push/v1/{server_id}` (приём push от нод).

> `GET /api/version` отдаёт версии + флаг `update_available`. Для пакетов с
> доступным обновлением добавляются заметки об изменениях: `notes` (commit-message
> FontaineRTC), `binary_notes` (release-body olcrtc), `wdtt.notes` (release-body
> WDTT). Строки `Co-Authored-By:` из них вырезаются. Их показывает окно
> «Доступно обновление».

### Админка
- `GET /api/data` — агрегированный дашборд (серверы, группы, инстансы, версии);
  каждый сервер содержит блок `wdtt` (статус + пользователи WDTT)
- `POST /api/groups/{add,edit,delete}` — при первой установке группа `SP-01`
  создаётся автоматически
- `POST /api/servers/{add,edit,delete,update,update-all}`
- `POST /api/node/{action}` — прокси действий на ноду: get-user, set-user,
  create-user, start-user, stop-user, delete-user, start-all, stop-all,
  restart-all, **wdtt-status, wdtt-list, wdtt-add, wdtt-del, wdtt-toggle**
- `POST /api/jitsi-domains/broadcast`, `POST /api/tg-settings`, `POST /api/tg-updates`
- `POST /api/poll-interval`, `POST /api/update` (только FontaineRTC панели)
- `GET/POST /api/subscription` — настройки раздачи olcrtc-подписки (агрегат всех нод)

### Нода
- `GET /api/status` — инстансы + ресурсы + jitsi_domains
- `POST /api/users/add`, `POST /api/users/{start,stop,delete}/{uid}`
- `POST /api/users/{start-all,stop-all,restart-all}`
- `POST /api/users/config/{uid}` — изменить настройки инстанса
- `GET /api/config`, `POST /api/config/save`, `GET /api/genkey`
- `GET /api/logs/stream/{uid}` (SSE), `GET /api/logs/download[/{uid}|-all]`
- `POST /api/update` (FontaineRTC + olcrtc + WDTT)
- `GET/POST /api/subscription` — настройки раздачи olcrtc-подписки (свои инстансы)

> **Подписка olcrtc** (`/api/subscription`: `{enabled, name, refresh, port}`)
> поднимает **второй HTTP-сервер на отдельном порту** (по умолчанию 8081), который
> отдаёт `text/plain` файл подписки (формат olcrtc `docs/sub.md`) по `GET /`.
> Эндпоинт публичный (без токена); порт включается/меняется на лету. Node отдаёт
> свои инстансы, admin — со всех нод.

#### WDTT (нода)
- `GET /api/wdtt` — статус + пользователи + версия
- `GET /api/wdtt/installing` — статус фоновой установки
- `POST /api/wdtt/users/{add,delete,toggle}` — CRUD паролей (add принимает
  `vk_hash` и возвращает `uri`, если хеш задан)
- `POST /api/wdtt/{install,uninstall}` — установка/удаление сервиса WDTT
- `GET /api/wdtt/logs/stream` (SSE), `GET /api/wdtt/logs/download`

> SSE и скачивания принимают токен в query (`?token=…`) — у EventSource/ссылок
> нет заголовков.
