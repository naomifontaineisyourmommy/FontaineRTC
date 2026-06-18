# FontaineRTC

Единая панель управления [OlcRTC](https://github.com/openlibrecommunity/olcrtc) —
одна кодовая база с **двумя режимами работы**:

- **node** — запускает экземпляры `olcrtc` на VPS и (опционально) VPN-протокол
  **WDTT** (WireGuard, замаскированный под видеозвонок ВКонтакте);
- **admin** — мониторит и управляет десятками нод из единого интерфейса.

Один бинарный пакет `fontaine`, роль выбирается переменной `FONTAINE_ROLE`.
Общий React-SPA для обеих ролей с переключаемыми цветовыми темами.

## Установка на сервер (Linux, root)

Всё подтягивается из репозитория автоматически. На ноде установщик ставит сразу
**FontaineRTC + olcrtc + WDTT**: бинарник `olcrtc` берётся свежий из релизов
[OlcRTC-AdvancedInteractive](https://github.com/naomifontaineisyourmommy/OlcRTC-AdvancedInteractive/releases),
а `wdtt-server` — из последнего релиза апстрима
[proxy-turn-vk-android](https://github.com/amurcanov/proxy-turn-vk-android).

```sh
# Нода (запускает olcrtc на этом VPS)
curl -fsSL https://raw.githubusercontent.com/naomifontaineisyourmommy/FontaineRTC/master/deploy/install.sh | sudo FONTAINE_ROLE=node bash

# Admin-панель (мониторинг и управление нодами)
curl -fsSL https://raw.githubusercontent.com/naomifontaineisyourmommy/FontaineRTC/master/deploy/install.sh | sudo FONTAINE_ROLE=admin bash
```

После установки выводятся **адрес панели**, **пароль** и **API-ключ** (один раз).
Admin за HTTPS: добавьте `ADMIN_DOMAIN=panel.example.com` (нужен nginx + сертификат
Let's Encrypt) — установщик настроит reverse-proxy.

**Обновление** (то же делает кнопка «↺ Обновить» в интерфейсе). На ноде проверяет
и обновляет всё сразу — FontaineRTC, olcrtc и WDTT (WDTT трогается только если
вышла новая версия); в режиме admin обновляется лишь сама панель:

```sh
sudo bash /opt/fontaine/deploy/update.sh
```

**Удаление** (данные сохраняются; `--purge` — удалить всё). На ноде удаляет и
olcrtc, и WDTT:

```sh
sudo bash /opt/fontaine/deploy/uninstall.sh           # сохранить config/data
sudo bash /opt/fontaine/deploy/uninstall.sh --purge   # удалить полностью
```

> Если шелл ругается на `/dev/fd/63` (нет поддержки `<(...)` — бывает в контейнерах),
> используется форма выше через `curl … | … bash`. Альтернатива — скачать и запустить:
> `curl -fsSL <url> -o i.sh && FONTAINE_ROLE=node bash i.sh`.

Управление сервисом: `systemctl status fontaine` · `journalctl -fu fontaine`.

## Стек

- Backend: **FastAPI** (один пакет `fontaine`, роль выбирается через `FONTAINE_ROLE`)
- Frontend: **React + Vite + TypeScript** (общий SPA для обеих ролей)
- БД: **SQLite** (stdlib `sqlite3`); деплой — `deploy/install.sh` или **Docker**
- Протокол node↔admin: Hash-CTR + HMAC-SHA256, защита от replay (`ts` ±60с)

Подробнее — [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md),
[docs/PROTOCOL.md](docs/PROTOCOL.md), [docs/API.md](docs/API.md) и
[docs/THEMES.md](docs/THEMES.md).

## Темы оформления

В интерфейсе (🎨 в шапке) переключаются темы. Встроенные: **Тёмная**, **Светлая**,
**Розовая**. Можно **скачать шаблон** текущей темы (JSON с описанием каждого
элемента) и **загрузить свою** тему файлом — она сохраняется локально в браузере.
Каждый элемент интерфейса описан семантическим токеном — см. [docs/THEMES.md](docs/THEMES.md).

## Структура

```
backend/    FastAPI-приложение (fontaine: core / node / admin / updater)
frontend/   React SPA (Vite); собранный dist закоммичен (сервер без Node)
deploy/     install.sh / update.sh / uninstall.sh, systemd unit, nginx-пример
docs/       ARCHITECTURE / PROTOCOL / API / THEMES
```

## Быстрый старт (разработка)

```sh
# Backend (роль node по умолчанию)
cd backend
python -m venv .venv && . .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
FONTAINE_ROLE=node python -m fontaine            # http://localhost:8080/healthz
pytest

# Frontend
cd ../frontend
npm install
npm run dev                                       # http://localhost:5173 (проксирует на :8080)
```

## Docker (обе роли локально)

```sh
docker compose up --build
# admin -> http://localhost:8080 , node -> http://localhost:8081
```

## Возможности

- Роль **node**: управление инстансами `olcrtc` (создание/настройка/запуск,
  live-логи по SSE), VPN-протокол **WDTT** (установка, CRUD-паролей, ссылки
  `wdtt://`, логи), watchdog с авто-рестартом, push состояния на admin.
- Роль **admin**: дашборд по группам и серверам (push + fallback-поллинг),
  удалённое проксирование действий на ноды (olcrtc и WDTT), Telegram-алерты,
  внешний зашифрованный API (`/api/v1`). Первая группа `SP-01` создаётся
  автоматически.
- Общее: переключаемые цветовые темы с экспортом/импортом, единый апдейтер
  (FontaineRTC + olcrtc + WDTT), 36 тестов (юнит + e2e node↔admin).

---

## Благодарности

Проект основан на панелях [tankionline2005](https://github.com/tankionline2005)
— **OlcRTC-VPS** и **OlcRTC-AdminVPS**. Спасибо за предоставленный код, который
послужил основой для FontaineRTC.

Сам OlcRTC — проект [zarazaex](https://github.com/zarazaex69) /
[openlibrecommunity](https://github.com/openlibrecommunity). Серверная часть WDTT
— [amurcanov/proxy-turn-vk-android](https://github.com/amurcanov/proxy-turn-vk-android).
