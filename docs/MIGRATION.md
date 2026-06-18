# План миграции функционала (по частям)

Перенос из `OlcRTC-VPS` (node) и `OlcRTC-AdminVPS` (admin) в единый `fontaine`.
Отмечай галочками по мере выполнения.

## Фаза 1 — Скелет + общее ядро ✅ (этот коммит)
- [x] Структура репозитория, git init
- [x] `core/crypto.py` — Hash-CTR + HMAC (перенос 1:1) + тесты
- [x] `core/uri.py` — сборка olcrtc:// URI (перенос 1:1) + тесты
- [x] `core/compat.py` — матрица совместимости + тесты
- [x] `core/security.py` — PBKDF2-пароль, rate-limit, сессии
- [x] `config.py`, `app.py` (диспетчер ролей), `__main__.py`
- [x] db base + модели (Group, Server, Instance — каркас)
- [x] Docker, .env.example, .gitignore, deploy-заглушки
- [x] docs: ARCHITECTURE, PROTOCOL, MIGRATION

## Фаза 2 — Роль node (backend) ✅ (кроме update_panel → фаза 5)
- [x] Модель `Instance` целиком (`node/instance.py`: template + public/options/full)
- [x] `node/yaml_writer.py` — генерация `<uid>.yaml` (перенос 1:1) + тесты
- [x] `node/manager.py` — реестр процессов, lifecycle, парсинг логов (room/peers/jitsi/wb), персистентность (SQLite kv)
- [x] `node/workers.py` — watchdog (10с, anti-loop 5×<30с) + traffic monitor (RX/TX по pid)
- [x] recover() — восстановление инстансов после рестарта/ребута
- [x] SSE-стрим логов + скачивание одного лога
- [x] `node/push.py` — push состояния и error-push на admin (+ heartbeat 30с)
- [x] `/api/v1`: list, get_user, set_user, create_user, start/stop/delete_user, start/stop/restart_all, set_jitsi_domains, set_push_target
- [x] WB owner-mode (wb_token), Jitsi-домены, max_session_duration
- [x] Смоук-тест: create/get/set/list/delete + compat + replay guard — проходит
- [ ] `update_panel` — заменяется деплой-пайплайном (фаза 5)
- [ ] zip-скачивание логов всех инстансов (мелочь, до фазы 4/6)

## Фаза 3 — Роль admin (backend) ✅
- [x] `admin/db.py` — Group/Server в SQLite (stdlib sqlite3, WAL, checkpoint)
- [x] `admin/config_store.py` — изменяемый config.json (пароль/ключ/poll/panel_url/tg)
- [x] `admin/manager.py` — клиент к нодам, кэш, поллер (fallback + перерегистрация push), telegram, агрегация
- [x] `admin/router.py` — приём `/push/v1/{sid}` (state + error→TG), `/api/login` (сессии+rate-limit), `/api/data`
- [x] group/server CRUD, проксирование `/api/node/{action}` на ноды
- [x] массовые операции, рассылка Jitsi-доменов, update panel (один/все)
- [x] MasterDNSVPN агрегация, внешний `/api/v1` (list)
- [x] `admin/flags.py` — страна→флаг
- [x] Тесты: CRUD, приём push, bad-key/unknown-server, external list — проходят (25 всего)
- [ ] WAL-миграция из старого data.db формата (тривиально совместимо — схема та же)

## Фаза 4 — Frontend ✅
- [x] Система тем: реестр токенов (каждый элемент описан), Тёмная/Светлая/Розовая
- [x] Переключение тем, скачивание шаблона (JSONC с описаниями), загрузка своей темы (валидация, localStorage)
- [x] Общий каркас: логин (X-Token), layout, toasts, детекция роли через /healthz
- [x] API-клиент (token в header; ?token= для SSE/скачиваний)
- [x] NodeDashboard: вкладки инстансов, сайдбар настроек, SSE-логи, массовые кнопки, глоб. настройки
- [x] AdminDashboard: галерея серверов, группы, поиск, окно деталей, модалки инстансов, TG, Jitsi-домены, интервал
- [x] Бэкенд: добавлен веб-API ноды (парольный) для SPA; отдача собранного dist из FastAPI
- [x] Сборка: `npm run build` (tsc strict + vite) — без ошибок; backend отдаёт SPA
- [ ] Доп. полировка UI/адаптив, выбор/редактор тем «вживую» (фаза 6)

## Фаза 5 — Деплой
- [ ] Dockerfile(ы) + multi-stage сборка фронтенда
- [ ] `install.sh`: генерация ключей, вывод один раз, frontend build
- [ ] nginx/HTTPS автонастройка (admin), UFW, systemd
- [ ] `update.sh`-эквивалент

## Фаза 6 — Паритет и тесты ✅
- [x] Тесты ядра: crypto (round-trip/tamper/replay), uri, compat
- [x] Тесты ноды: /api/v1 CRUD + compat + replay + bad-key; list отдаёт wb_token/jitsi_domains
- [x] Тесты админки: login, CRUD групп/серверов, приём push, внешний list
- [x] Тесты сессий (stateless, переживают рестарт) и пароля
- [x] **E2E node↔admin** по реальному шифрованному протоколу (test_e2e): регистрация,
      poll, прокси create/delete, агрегация /api/data, внешний /api/v1 list — 29 тестов
- [x] Живая проверка по реальному HTTP (отдельный процесс ноды) — протокол ок
- [x] Документация API — [API.md](API.md)
- [ ] Опционально: e2e через docker-compose (двумя контейнерами)

## Фаза 7 — Модернизация (опционально)
- [ ] Новый транспорт протокола (mTLS / JWT) вместо Hash-CTR
- [ ] Postgres-вариант, RBAC, метрики/Prometheus
```