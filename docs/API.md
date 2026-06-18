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
  "masterdnsvpn": [ {"domain": "…", "key": "…"}, … ]
}
```
`status=active`, если инстанс запущен **и** URI готова. Агрегируется по всем нодам.
`peers_devices` — HWID подключённых клиентов.

> Это весь внешний API админки — намеренно минимальный (как в оригинале), только чтение.

---

## 2. Внешний зашифрованный API ноды — `POST /api/v1`

Им пользуется админка. Шифрование — `api_key` ноды. Действия:

| Действие | Назначение |
|:--|:--|
| `list` | инстансы (полный конфиг inline) + `server` (CPU/RAM) + `jitsi_domains` |
| `get_user` / `set_user` | прочитать / изменить инстанс |
| `create_user` | создать (по умолчанию jitsi+datachannel) |
| `start_user` / `stop_user` / `delete_user` | управление одним |
| `start_all` / `stop_all` / `restart_all` | массовые |
| `set_jitsi_domains` | список доменов |
| `set_push_target` | URL админки для push (`""` = выкл) |
| `update_panel` | обновление панели (гейтится версией) |

---

## 3. Внутренний web-API (для SPA, авторизация по `X-Token`)

Логин: `POST /api/login {password}` → `{token}` (stateless, переживает рестарт).
Открытые (без токена): `GET /healthz`, `GET /api/updating`, `GET /api/version`,
а у админки ещё `POST /push/v1/{server_id}` (приём push от нод).

### Админка
- `GET /api/data` — агрегированный дашборд (серверы, группы, инстансы, версии)
- `POST /api/groups/{add,edit,delete}`
- `POST /api/servers/{add,edit,delete,update,update-all}`
- `POST /api/node/{action}` — прокси действия на ноду (get-user, set-user,
  create-user, start-user, stop-user, delete-user, start-all, stop-all, restart-all)
- `POST /api/jitsi-domains/broadcast`, `POST /api/tg-settings`, `POST /api/tg-updates`
- `POST /api/poll-interval`, `POST /api/update`

### Нода
- `GET /api/status` — инстансы + ресурсы + jitsi_domains + masterdnsvpn
- `POST /api/users/add`, `POST /api/users/{start,stop,delete}/{uid}`
- `POST /api/users/{start-all,stop-all,restart-all}`
- `POST /api/users/config/{uid}` — изменить настройки инстанса
- `GET /api/config`, `POST /api/config/save`, `GET /api/genkey`
- `GET /api/logs/stream/{uid}` (SSE), `GET /api/logs/download[/{uid}|-all]`
- `POST /api/update`

> SSE и скачивания принимают токен в query (`?token=…`) — у EventSource/ссылок
> нет заголовков.
