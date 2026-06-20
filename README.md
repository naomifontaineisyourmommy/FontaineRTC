# FontaineRTC

Единая панель управления [OlcRTC](https://github.com/openlibrecommunity/olcrtc) и [WDTT](https://github.com/amurcanov/proxy-turn-vk-android)

- **node** — запускает экземпляры `olcrtc` и VPN-протокол `WDTT` на VPS;
- **admin** — мониторит и управляет десятками нод из единого интерфейса.

<img width="1920" height="920" alt="Image" src="https://github.com/user-attachments/assets/1bee96b0-c4e9-44dd-a419-cba34b839be1" />
<img width="1920" height="920" alt="Image" src="https://github.com/user-attachments/assets/f7ec9fa0-29a3-4e0a-85b9-b94b0b8a1692" />
<img width="1920" height="920" alt="Image" src="https://github.com/user-attachments/assets/4f706255-5968-4dca-9da5-528e0f2e0107" />
<img width="1920" height="920" alt="Image" src="https://github.com/user-attachments/assets/7abd7c20-30b6-421b-9c9c-4f4d0129c8c2" />
<img width="1920" height="920" alt="Image" src="https://github.com/user-attachments/assets/454e46ab-4199-46ba-96a2-65b837be2605" />

## Установка на сервер (Linux, root)

Всё подтягивается из репозитория автоматически. На ноде установщик ставит сразу
**FontaineRTC + olcrtc + WDTT**: бинарник `olcrtc` берётся свежий из релизов
[OlcRTC-AdvancedInteractive](https://github.com/naomifontaineisyourmommy/OlcRTC-AdvancedInteractive/releases),
а `wdtt-server` — из последнего релиза апстрима
[proxy-turn-vk-android](https://github.com/amurcanov/proxy-turn-vk-android).


# Установка в режиме Node (запускает olcrtc и wdtt на этом VPS)
```sh
curl -fsSL https://raw.githubusercontent.com/naomifontaineisyourmommy/FontaineRTC/master/deploy/install.sh | sudo FONTAINE_ROLE=node bash
```

# Установка в режиме Admin (мониторинг и управление нодами)
```sh
curl -fsSL https://raw.githubusercontent.com/naomifontaineisyourmommy/FontaineRTC/master/deploy/install.sh | sudo FONTAINE_ROLE=admin bash
```

После установки выводятся **адрес панели**, **пароль** и **API-ключ** (один раз).
Панель работает по HTTP; если нужен TLS — поставьте перед ней свой reverse-proxy.

**Обновление** (то же делает кнопка «↺ Обновить» в интерфейсе). На ноде проверяет
и обновляет всё сразу — FontaineRTC, olcrtc и WDTT (бинарники трогаются только если
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

Управление сервисом: `systemctl status fontaine` · `journalctl -fu fontaine`.

**Подписки OlcRTC.** В интерфейсе («Настроить подписку OlcRTC») можно включить
раздачу подписки — панель поднимает второй HTTP-сервер на отдельном порту
(по умолчанию 8081) и отдаёт по нему `text/plain` файл со всеми инстансами
(формат olcrtc `sub.md`). В режиме node раздаются свои инстансы, в режиме admin —
со всех нод. Порт меняется на лету. Раздача идёт по HTTP; нужен TLS — поставьте
свой reverse-proxy.


---

## Благодарности

Проект основан на панелях [tankionline2005](https://github.com/tankionline2005)
— **OlcRTC-VPS** и **OlcRTC-AdminVPS**. Спасибо за предоставленный код и идеи, которые
послужили основой для FontaineRTC.

Сам OlcRTC — проект [zarazaex](https://github.com/zarazaex69) /
[openlibrecommunity](https://github.com/openlibrecommunity).
Серверная часть WDTT
— [amurcanov/proxy-turn-vk-android](https://github.com/amurcanov/proxy-turn-vk-android).
