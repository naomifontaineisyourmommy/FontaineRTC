# FontaineRTC

Единая панель управления [OlcRTC](https://github.com/openlibrecommunity/olcrtc) —
идейное продолжение и объединение двух проектов в одну кодовую базу с **двумя
режимами работы**:

- **node** — запускает экземпляры `olcrtc` на VPS (бывший **OlcRTC-VPS**);
- **admin** — мониторит и управляет десятками нод из единого интерфейса
  (бывший **OlcRTC-AdminVPS**).

> [!CAUTION]
> Проект в активной разработке (миграция по фазам). Сейчас готов **скелет +
> общее ядро** — см. [docs/MIGRATION.md](docs/MIGRATION.md).

## Стек

- Backend: **FastAPI** (один пакет `fontaine`, роль выбирается через `FONTAINE_ROLE`)
- Frontend: **React + Vite + TypeScript** (общий SPA для обеих ролей)
- БД: **SQLite** (SQLAlchemy), деплой через **Docker** или `deploy/install.sh`
- Протокол node↔admin: совместим с оригиналами (Hash-CTR + HMAC-SHA256)

Подробнее — [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) и
[docs/PROTOCOL.md](docs/PROTOCOL.md).

## Структура

```
backend/    FastAPI-приложение (fontaine: core / node / admin / db)
frontend/   React SPA (Vite)
deploy/     install.sh, systemd unit, nginx-пример
docs/        ARCHITECTURE / PROTOCOL / MIGRATION
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
| 3    | Роль admin (backend)             | ⏳ |
| 4    | Frontend                         | ⏳ |
| 5    | Деплой                           | ⏳ |
| 6    | Паритет и тесты                  | ⏳ |
