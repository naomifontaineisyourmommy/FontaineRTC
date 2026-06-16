# FontaineRTC

Единая панель управления [OlcRTC](https://github.com/openlibrecommunity/olcrtc) —
идейное продолжение и объединение двух проектов в одну кодовую базу с **двумя
режимами работы**:

- **node** — запускает экземпляры `olcrtc` на VPS (бывший **OlcRTC-VPS**);
- **admin** — мониторит и управляет десятками нод из единого интерфейса
  (бывший **OlcRTC-AdminVPS**).

> [!CAUTION]
> Проект в активной разработке. Бэкенд обеих ролей, фронтенд с темами и
> установка/обновление/удаление готовы — см. [docs/MIGRATION.md](docs/MIGRATION.md).

## Установка на сервер (Linux, root)

Всё подтягивается из репозитория автоматически; бинарник `olcrtc` берётся свежий
из релизов
[OlcRTC-AdvancedInteractive](https://github.com/naomifontaineisyourmommy/OlcRTC-AdvancedInteractive/releases).

```sh
# Нода (запускает olcrtc на этом VPS)
curl -fsSL https://raw.githubusercontent.com/naomifontaineisyourmommy/FontaineRTC/master/deploy/install.sh | sudo FONTAINE_ROLE=node bash

# Admin-панель (мониторинг и управление нодами)
curl -fsSL https://raw.githubusercontent.com/naomifontaineisyourmommy/FontaineRTC/master/deploy/install.sh | sudo FONTAINE_ROLE=admin bash
```

После установки выводятся **адрес панели**, **пароль** и **API-ключ** (один раз).
Admin за HTTPS: добавьте `ADMIN_DOMAIN=panel.example.com` (нужен nginx + сертификат
Let's Encrypt) — установщик настроит reverse-proxy.

**Обновление** (то же делает кнопка «↺ Обновить» в интерфейсе — подтягивает код из
репо + свежий бинарник + перезапуск):

```sh
sudo bash /opt/fontaine/deploy/update.sh
```

**Удаление** (данные сохраняются; `--purge` — удалить всё):

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
- Протокол node↔admin: совместим с оригиналами (Hash-CTR + HMAC-SHA256)

Подробнее — [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md),
[docs/PROTOCOL.md](docs/PROTOCOL.md) и [docs/THEMES.md](docs/THEMES.md).

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
docs/        ARCHITECTURE / PROTOCOL / THEMES / MIGRATION
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

## Статус

| Фаза | Описание                         | Статус |
|:-----|:---------------------------------|:------:|
| 1    | Скелет + общее ядро (crypto/uri/compat) | ✅ |
| 2    | Роль node (backend)              | ✅ |
| 3    | Роль admin (backend)             | ✅ |
| 4    | Frontend + темы                  | ✅ |
| 5    | Деплой (install/update/uninstall) | ✅ |
| 6    | Паритет и тесты                  | ⏳ |

---

## Благодарности

Проект основан на панелях [tankionline2005](https://github.com/tankionline2005)
— **OlcRTC-VPS** и **OlcRTC-AdminVPS**. Спасибо за предоставленный код, который
послужил основой для FontaineRTC.

Сам OlcRTC — проект [zarazaex](https://github.com/zarazaex69) /
[openlibrecommunity](https://github.com/openlibrecommunity).
