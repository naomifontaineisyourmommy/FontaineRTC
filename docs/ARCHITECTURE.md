# FontaineRTC — Архитектура и план

FontaineRTC — идейное продолжение и объединение двух проектов:

- **OlcRTC-VPS** — панель-**нода**: запускает экземпляры бинарника `olcrtc` на VPS, по одному на пользователя.
- **OlcRTC-AdminVPS** — **центральная** панель: мониторит десятки нод (push + poll), управляет инстансами удалённо, TG-алерты, группы.

В FontaineRTC это **единая кодовая база с двумя режимами работы** (`role = node | admin`), современный стек и общее ядро.

---

## 1. Модель объединения: один код, два режима

При установке/запуске выбирается роль:

| Роль    | Что делает                                                                 |
|:--------|:--------------------------------------------------------------------------|
| `node`  | Управляет локальными `olcrtc`-процессами (бывший OlcRTC-VPS).             |
| `admin` | Мониторит и управляет нодами (бывший OlcRTC-AdminVPS).                    |

Один и тот же backend-пакет `fontaine`. Роль выбирает, какие роутеры и фоновые
воркеры поднимать. Общие модули (`core/`) переиспользуются обеими ролями —
именно здесь устраняется дублирование оригиналов (крипто, конфиг, URI, матрица
совместимости, безопасность).

> На будущее заложена возможность роли `master` (node+admin одновременно на одном
> сервере) — обе роли монтируются в одно приложение. В первой версии не включаем.

---

## 2. Технологический стек

| Слой          | Выбор                                  | Причина                                               |
|:--------------|:---------------------------------------|:------------------------------------------------------|
| Backend       | **FastAPI** (ASGI, uvicorn)            | async, нативные SSE/WebSocket, типобезопасность       |
| Валидация     | **Pydantic v2** / pydantic-settings    | модели запросов, конфиг из env                        |
| БД            | **SQLite** (stdlib `sqlite3`, WAL)     | как в оригинале; синхронно; миграция на Postgres при росте |
| Frontend      | **React + Vite + TypeScript** (SPA)    | реал-тайм дашборды, компонентный UI                   |
| Состояние UI  | TanStack Query + Zustand               | кэш/поллинг и локальный стейт                          |
| Деплой        | **Docker Compose**                     | переносимость; для bare-metal — `deploy/install.sh`   |
| Реал-тайм     | SSE (логи), poll каждые 5с (дашборды)  | как в оригинале                                       |

> Решение зафиксировано как дефолт; меняется правкой этого документа до начала миграции функционала.

---

## 3. Структура репозитория

```
FontaineRTC/
├── README.md
├── docker-compose.yml
├── .env.example
├── .gitignore
├── backend/
│   ├── pyproject.toml
│   ├── Dockerfile
│   ├── fontaine/
│   │   ├── __main__.py          # entrypoint: парсит роль, поднимает uvicorn
│   │   ├── config.py            # Settings (pydantic-settings), ROLE
│   │   ├── app.py               # фабрика FastAPI, монтаж роутеров по роли
│   │   ├── core/                # ОБЩЕЕ ЯДРО (обе роли)
│   │   │   ├── crypto.py        # Hash-CTR + HMAC-SHA256 (перенесено 1:1)
│   │   │   ├── security.py      # хэш пароля, сессии/токены, rate-limit
│   │   │   ├── uri.py           # сборка/разбор olcrtc:// URI
│   │   │   └── compat.py        # матрица carrier × transport
│   │   ├── db/
│   │   │   ├── base.py          # engine, session
│   │   │   └── models.py        # groups, servers, instances
│   │   ├── node/                # РОЛЬ NODE
│   │   │   ├── router.py        # /api/v1, /sse, управление инстансами
│   │   │   ├── manager.py       # реестр процессов, watchdog, восстановление
│   │   │   ├── process.py       # запуск/остановка olcrtc, чтение логов
│   │   │   ├── yaml_writer.py   # генерация <uid>.yaml для бинарника
│   │   │   └── push.py          # push состояния на admin
│   │   ├── admin/               # РОЛЬ ADMIN
│   │   │   ├── router.py        # /api/v1, серверы/группы, проксирование на ноды
│   │   │   ├── push_in.py       # приём /push/v1/{server_id}
│   │   │   ├── poller.py        # fallback-поллинг нод
│   │   │   ├── nodes.py         # клиент к API ноды
│   │   │   └── telegram.py      # алерты в Telegram
│   │   └── web.py               # отдача собранного SPA
│   └── tests/
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── index.html
│   └── src/
│       ├── main.tsx, App.tsx
│       ├── api/                 # клиент к backend
│       ├── components/          # переиспользуемые (плитки, модалки, toasts)
│       ├── pages/               # NodeDashboard, AdminDashboard
│       └── lib/
├── deploy/
│   ├── install.sh              # bare-metal установка (venv + systemd + nginx)
│   ├── fontaine.service
│   └── nginx.conf.example
└── docs/
    ├── ARCHITECTURE.md         # этот файл
    ├── PROTOCOL.md             # протокол node↔admin (push + API)
    └── MIGRATION.md            # чеклист переноса функционала по частям
```

---

## 4. Протокол node ↔ admin (сохраняем совместимость)

На время миграции оставляем проверенную схему оригинала, вынесенную в `core/crypto.py`:

- Тело: `base64url( nonce(16) | HMAC-SHA256(32) | ciphertext )`.
- Шифр: Hash-CTR (XOR с SHA256-keystream). Ключ — 64-символьный HEX (`api_key`).
- Защита от replay: поле `ts` в каждом запросе, допуск ±60 с.
- Действия API ноды и формат push сохраняются (см. `docs/PROTOCOL.md`).

Это позволяет новому admin работать со старыми нодами и наоборот в переходный период.
Модернизация транспорта (mTLS/JWT) — отдельным этапом после полной миграции.

---

## 5. Контракт с бинарником `olcrtc` (роль node)

Не меняется — фиксируется внешним бинарником:

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

## 6. URI-формат (перенесено 1:1)

```
olcrtc://<carrier>?<transport><payload>@<roomID>#<key>
```

`<payload>` = `<key=value&...>` для vp8channel/seichannel/videochannel; для
datachannel отсутствует. См. `core/uri.py`.

---

## 7. Матрица совместимости (перенесено 1:1)

| Транспорт    | WBStream | Jitsi | Telemost |
|:-------------|:--------:|:-----:|:--------:|
| datachannel  | ✗        | ✓     | ✗        |
| vp8channel   | ✓        | ✓     | ✓        |
| seichannel   | ✓        | ✓     | ✗        |
| videochannel | ✓        | ✓     | ✓        |

См. `core/compat.py`.

---

## 8. План миграции (по частям)

Подробный чеклист — `docs/MIGRATION.md`. Крупными вехами:

1. **Скелет + общее ядро** (этот коммит): структура, `core/` (crypto/uri/compat),
   конфиг, фабрика приложения, заглушки роутеров, docker, install.sh, docs.
2. **Роль node — backend**: модели инстансов, process manager, watchdog,
   yaml_writer, SSE-логи, `/api/v1`, push исходящий.
3. **Роль admin — backend**: модели групп/серверов, приём push, poller,
   клиент к нодам, TG-алерты, `/api/v1`.
4. **Frontend**: общий каркас, NodeDashboard, AdminDashboard, реал-тайм.
5. **Деплой**: Dockerfile'ы, compose, install.sh, nginx, systemd.
6. **Паритет и тесты**: сверка с оригиналами фича-в-фичу, тесты крипто/URI/API.
7. **Модернизация**: (опционально) новый транспорт протокола, Postgres, RBAC.
```

---

## Благодарности

Архитектура и логика портированы с панелей
[tankionline2005](https://github.com/tankionline2005) (**OlcRTC-VPS** и
**OlcRTC-AdminVPS**). Благодарим за предоставленный код, ставший основой FontaineRTC.