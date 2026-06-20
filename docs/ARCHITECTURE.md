# FontaineRTC — Архитектура


## 1. Один код, два режима

Роль выбирается переменной окружения `FONTAINE_ROLE` при запуске:

| Роль    | Что делает                                                                |
|:--------|:--------------------------------------------------------------------------|
| `node`  | Управляет локальными `olcrtc`-процессами и сервисом WDTT на этом VPS.      |
| `admin` | Мониторит и удалённо управляет нодами (push + поллинг), TG-алерты об ошибках, группы. |

Один backend-пакет `fontaine`. `app.py` по роли монтирует нужный роутер
(`node/router.py` или `admin/router.py`) и поднимает фоновые воркеры. Общее ядро
`core/` (crypto, security, URI, матрица совместимости) переиспользуется обеими
ролями — здесь устранено дублирование исходных панелей.

---

## 2. Технологический стек

| Слой      | Выбор                                   |
|:----------|:----------------------------------------|
| Backend   | **FastAPI** (ASGI, uvicorn), Pydantic v2 / pydantic-settings |
| БД        | **SQLite** (stdlib `sqlite3`, WAL) — только роль admin (группы/серверы) |
| Frontend  | **React + Vite + TypeScript** (общий SPA, локальный стейт + поллинг) |
| Реал-тайм | SSE (логи olcrtc и WDTT), поллинг дашбордов раз в ~4с, push нода→admin |
| Деплой    | `deploy/install.sh` (venv + systemd) или **Docker Compose** |

Состояние сессий — stateless (HMAC над `issued|nonce` с `api_key`), переживает
рестарт. Собранный `frontend/dist` закоммичен, чтобы на сервере не требовался Node.

---

## 3. Структура репозитория

```
FontaineRTC/
├── README.md
├── docker-compose.yml · .env.example · .gitignore
├── backend/
│   ├── pyproject.toml · Dockerfile
│   ├── fontaine/
│   │   ├── __main__.py          # entrypoint: роль + uvicorn
│   │   ├── config.py            # Settings (pydantic-settings), ROLE
│   │   ├── app.py               # фабрика FastAPI, монтаж роутеров/воркеров по роли
│   │   ├── updater.py           # self-update (git reset --hard) + версии/обновления
│   │   ├── subserver.py         # второй HTTP-порт: раздача olcrtc-подписки (sub.md)
│   │   ├── web.py               # отдача собранного SPA
│   │   ├── core/                # ОБЩЕЕ ЯДРО (обе роли)
│   │   │   ├── crypto.py        # Hash-CTR + HMAC-SHA256
│   │   │   ├── security.py      # хэш пароля, stateless-сессии, rate-limit
│   │   │   ├── uri.py           # сборка/разбор olcrtc:// URI
│   │   │   └── compat.py        # матрица carrier × transport
│   │   ├── node/                # РОЛЬ NODE
│   │   │   ├── router.py        # /api/v1, web-API, SSE-логи
│   │   │   ├── manager.py       # реестр процессов olcrtc, save/restore
│   │   │   ├── instance.py      # модель инстанса, public/full проекции, URI
│   │   │   ├── yaml_writer.py   # генерация <uid>.yaml для бинарника
│   │   │   ├── store.py · sysinfo.py · push.py · workers.py
│   │   │   └── wdtt/            # ПОДСИСТЕМА WDTT
│   │   │       ├── installer.py # установка/удаление/версии wdtt-server
│   │   │       ├── manager.py   # статус сервиса + CRUD паролей
│   │   │       └── store.py     # passwords.json + сайдкар fontaine-meta.json
│   │   └── admin/               # РОЛЬ ADMIN
│   │       ├── router.py        # web-API, /api/v1, /push/v1, прокси на ноды
│   │       ├── manager.py       # кэш состояния нод, агрегация, поллер
│   │       ├── db.py            # группы/серверы (SQLite); сид группы SP-01
│   │       ├── config_store.py · flags.py
│   └── tests/                   # 36 тестов (crypto/uri/security/yaml/node/admin/wdtt/updater/e2e)
├── frontend/
│   └── src/                     # main.tsx, App.tsx, api/, components/, pages/, theme/, lib/, styles/
├── deploy/                      # install.sh / update.sh / uninstall.sh, fontaine.service
└── docs/                        # ARCHITECTURE / PROTOCOL / API / THEMES
```

---

## 4. Протокол node ↔ admin

Реализация шифрования — `core/crypto.py`; детали действий и push — `docs/PROTOCOL.md`.

- Тело: `base64url( nonce(16) | HMAC-SHA256(32) | ciphertext )`.
- Шифр: Hash-CTR (XOR с SHA256-keystream). Ключ — 64-символьный HEX (`api_key`).
- Защита от replay: поле `ts` (unix) в каждом запросе, допуск ±60 с.
- Admin проксирует действия на ноду через `POST /api/node/{action}` (включая WDTT).

---

## 5. Контракт с бинарником `olcrtc` (роль node)

Фиксируется внешним бинарником:

- Запуск: `./olcrtc-linux-amd64 <uid>.yaml`.
- Параметры передаются через YAML (`yaml_writer.py`), отражаются в URI.
- Runtime-данные парсятся из stdout/stderr регулярками:
  - Room ID (`To connect client use: -id ...`, `room created:`, `Created and connected to WB Stream room id:`)
  - Готовность Jitsi (`ready='true'`), `Link connected`
  - Онлайн-клиенты: `Current peers count: N, Devices: [...]`
  - Деградация WB-токена: `livekit reconnect failed`
- Watchdog: проверка каждые 10с, авто-рестарт при `auto_restart`, защита от
  цикла (5 падений подряд по <30с → авто-рестарт выключается).

---

## 6. URI-формат

```
olcrtc://<carrier>?<transport><payload>@<roomID>#<key>
```

`<payload>` = `<key=value&...>` для vp8channel/seichannel/videochannel; для
datachannel отсутствует. См. `core/uri.py`.

---

## 7. Матрица совместимости

| Транспорт    | WBStream | Jitsi | Telemost |
|:-------------|:--------:|:-----:|:--------:|
| datachannel  | ✗        | ✓     | ✗        |
| vp8channel   | ✓        | ✓     | ✓        |
| seichannel   | ✓        | ✓     | ✗        |
| videochannel | ✓        | ✓     | ✓        |

См. `core/compat.py`.

---

## 8. Подсистема WDTT (роль node)

WDTT — VPN на базе WireGuard, трафик которого замаскирован под видеозвонок
ВКонтакте. Управляется на ноде в Python (без мобильного приложения и Telegram-бота):

- **Установка** (`wdtt/installer.py`): из последнего релиза апстрима
  [proxy-turn-vk-android](https://github.com/amurcanov/proxy-turn-vk-android)
  скачивается `WDTT-universal.apk`, из него (stdlib `zipfile`) извлекаются
  `wdtt-server` и `deploy.sh`; `deploy.sh` поднимает systemd-сервис `wdtt.service`.
  Тег релиза запоминается как версия; APK удаляется.
- **Пользователи** (`wdtt/manager.py` + `wdtt/store.py`): «пользователь» = запись-
  пароль в `/etc/wdtt/passwords.json`. CRUD редактирует файл при остановленном
  сервисе и перезапускает его (сервер читает базу только при старте).
- **VK-хеш и ссылки**: сам wdtt-server VK-хеш не хранит, поэтому FontaineRTC
  держит его (и host) в сайдкаре `/etc/wdtt/fontaine-meta.json` — это позволяет
  восстановить готовую ссылку `wdtt://IP:DTLS:WG:TUN:ПАРОЛЬ:VK_HASH` для таблицы.
- **Жизненный цикл**: install/update/uninstall обрабатывают FontaineRTC + olcrtc +
  WDTT вместе; WDTT переустанавливается при обновлении только если вышел новый тег.

