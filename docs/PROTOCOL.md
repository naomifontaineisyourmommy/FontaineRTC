# Протокол node ↔ admin

Сохраняется совместимым с оригиналами (`OlcRTC-VPS` / `OlcRTC-AdminVPS`) на время
миграции. Реализация шифрования — `backend/fontaine/core/crypto.py`.

## Шифрование

Тело запроса и ответа:

```
base64url( nonce(16) | HMAC-SHA256(32) | ciphertext )
```

- Шифр: Hash-CTR (XOR с SHA256-keystream).
- Ключ: 64-символьный HEX (`api_key` ноды).
- Транспорт: `POST`, `Content-Type: text/plain`.
- Replay-защита: поле `ts` (unix-секунды) в каждом запросе, допуск ±60 с.

## API ноды — `POST /api/v1`

Действия (JSON внутри шифртекста, поле `action`):

| Действие            | Назначение                                            |
|:--------------------|:------------------------------------------------------|
| `list`              | список инстансов + статистика сервера                 |
| `get_user`          | полные настройки + статус + options (динамически)     |
| `set_user`          | импорт настроек инстанса                              |
| `create_user`       | создать инстанс (по умолчанию jitsi+datachannel)      |
| `start_user` / `stop_user` / `delete_user` | управление одним инстансом      |
| `start_all` / `stop_all` / `restart_all`   | массовые операции               |
| `set_jitsi_domains` | задать список Jitsi-доменов                           |
| `set_push_target`   | задать URL admin для push (`""` = выключить)          |
| `update_panel`      | скачать свежие файлы и перезапуститься                |

> `wb_token` хранится только на ноде и **не** отдаётся во внешний `list`.

## Push нода → admin — `POST /push/v1/{server_id}`

Тело зашифровано тем же `api_key`. Два типа:

**Тип 1 — состояние** (heartbeat 30с + при каждом изменении): `server`, `users[]`
(c `uri`, `running`, `uri_live`, `carrier`, `transport`, `uptime`, `peers_count`,
`peers_devices`, `traffic_rx/tx`), `masterdnsvpn` (объект или `null`).

**Тип 2 — ошибка процесса** (`type: "error"`): `user_id`, `carrier`, `transport`,
`error`. Admin шлёт Telegram-уведомление.

Ответы admin: `200 ok`, `400 Bad request` / `Timestamp expired`,
`404 Unknown server` (нода обязана отключить push и очистить URL).

## Внешний API admin — `POST /api/v1`

Действие `list` — агрегированный список всех пользователей со всех нод
(`client_id`, `uri`, `status` active/inactive, `peers_count`, `server_name`,
`server_country`, `group_id`) + массив `masterdnsvpn` со всех онлайн-нод.

> Подробные форматы полей — в README оригиналов, переносятся дословно в фазах 2–3.
```