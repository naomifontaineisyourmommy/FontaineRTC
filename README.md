# FontaineRTC

Единая панель управления [OlcRTC](https://github.com/openlibrecommunity/olcrtc) и [WDTT](https://github.com/amurcanov/proxy-turn-vk-android)

- **node** — запускает экземпляры `olcrtc` и VPN-протокол `WDTT` на VPS;
- **admin** — мониторит и управляет десятками нод из единого интерфейса.

<img width="1920" height="908" alt="Image" src="https://github.com/user-attachments/assets/b414851a-db78-4063-be0f-a43c5b418784" />
<img width="1920" height="908" alt="Image" src="https://github.com/user-attachments/assets/e27d8aa5-3560-486b-8ca0-211dc41d9b54" />
<img width="1920" height="908" alt="Image" src="https://github.com/user-attachments/assets/9bec48a6-08d9-461a-bd02-faa4f3a5bbce" />
<img width="1920" height="908" alt="Image" src="https://github.com/user-attachments/assets/cb6a1cb4-909a-4a1e-b55c-d31bf45d1668" />
<img width="1920" height="908" alt="Image" src="https://github.com/user-attachments/assets/9e4f916d-443d-40db-a52a-ce24c03671e8" />
<img width="1920" height="908" alt="Image" src="https://github.com/user-attachments/assets/fcba91e2-b3f5-479a-b1fb-14180a5a7004" />
<img width="1920" height="908" alt="Image" src="https://github.com/user-attachments/assets/c8191cf9-ee98-4a6c-bdd9-e9c7d1d9cd1d" />
<img width="1920" height="912" alt="Image" src="https://github.com/user-attachments/assets/bac6b2a6-e57e-4200-9044-60dca89ed36c" />

## Установка на сервер (Linux, root)

Всё подтягивается из репозитория автоматически. На ноде установщик ставит сразу
**FontaineRTC + olcrtc + WDTT**: бинарник `olcrtc` берётся свежий из релизов
[OlcRTC-AdvancedInteractive](https://github.com/naomifontaineisyourmommy/OlcRTC-AdvancedInteractive/releases),
а `wdtt-server` — из последнего релиза апстрима
[proxy-turn-vk-android](https://github.com/amurcanov/proxy-turn-vk-android).


### Установка в режиме Node (запускает olcrtc и wdtt на этом VPS)
```sh
curl -fsSL https://raw.githubusercontent.com/naomifontaineisyourmommy/FontaineRTC/master/deploy/install.sh | sudo FONTAINE_ROLE=node bash
```

### Установка в режиме Admin (мониторинг и управление нодами)
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
