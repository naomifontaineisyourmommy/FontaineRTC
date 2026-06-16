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

## Фаза 3 — Роль admin (backend)
- [ ] Модели Group/Server + миграция из старой data.db
- [ ] `admin/push_in.py` — приём `/push/v1/{server_id}`, кэш состояния
- [ ] `admin/poller.py` — fallback-поллинг, перерегистрация push
- [ ] `admin/nodes.py` — клиент к API ноды (все действия)
- [ ] `admin/telegram.py` — алерты, get chat ids
- [ ] `/api/login`, `/api/data` (агрегация), server/group CRUD, проксирование действий на ноды
- [ ] массовые операции, рассылка Jitsi-доменов, update panel (один/все)
- [ ] MasterDNSVPN агрегация, внешний `/api/v1` (list)

## Фаза 4 — Frontend
- [ ] Общий каркас: логин, layout, toasts, query-клиент
- [ ] NodeDashboard: вкладки инстансов, сайдбар настроек, SSE-логи, массовые кнопки
- [ ] AdminDashboard: галерея серверов, группы, поиск, окно деталей, модалки инстансов
- [ ] Реал-тайм (poll 5с, SSE), копирование URI, индикаторы live/online

## Фаза 5 — Деплой
- [ ] Dockerfile(ы) + multi-stage сборка фронтенда
- [ ] `install.sh`: генерация ключей, вывод один раз, frontend build
- [ ] nginx/HTTPS автонастройка (admin), UFW, systemd
- [ ] `update.sh`-эквивалент

## Фаза 6 — Паритет и тесты
- [ ] Сверка фича-в-фичу с README обоих оригиналов
- [ ] Тесты API ноды/админа, push-протокола, watchdog-логики
- [ ] E2E: node↔admin через docker-compose

## Фаза 7 — Модернизация (опционально)
- [ ] Новый транспорт протокола (mTLS / JWT) вместо Hash-CTR
- [ ] Postgres-вариант, RBAC, метрики/Prometheus
```