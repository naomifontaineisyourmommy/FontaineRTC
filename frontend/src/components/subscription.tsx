/** Shared "Настроить подписку OlcRTC" modal — used by the node olcrtc toolbar and
 *  the admin toolbar. Both talk to their own panel's /api/subscription, so the
 *  same component works for either role (node serves its own instances, admin the
 *  aggregate of every node). */

import { useEffect, useState } from "react";
import { apiGet, apiPost } from "../api/client";
import { Modal, Switch, copy, useToast } from "./ui";

interface Sub { enabled: boolean; name: string; refresh: string; port: number; }

const FALLBACK: Sub = { enabled: false, name: "FontaineRTC", refresh: "10m", port: 8081 };

export function SubscriptionModal({ onClose }: { onClose: () => void }) {
  const [s, setS] = useState<Sub | null>(null);
  const [saving, setSaving] = useState(false);
  const toast = useToast();

  useEffect(() => { apiGet("/api/subscription").then(setS).catch(() => setS(FALLBACK)); }, []);

  // The panel is reached at this hostname; the subscription is served on its own
  // port. The host part can't be hard-known server-side, so build it client-side.
  const url = s ? `http://${window.location.hostname}:${s.port}/` : "";

  const save = async () => {
    if (!s) return;
    setSaving(true);
    try {
      const r = await apiPost("/api/subscription", s);
      if (r.error) { toast.push(r.error, false); return; }
      setS(r);
      toast.push(r.enabled ? "Раздача подписки включена" : "Сохранено");
      onClose();
    } catch (e) {
      toast.push(e instanceof Error ? e.message : "Ошибка", false);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal title="Настроить подписку OlcRTC" onClose={onClose}
      footer={<button className="btn" disabled={saving || !s} onClick={save}>Сохранить</button>}>
      {!s ? <div className="empty">Загрузка…</div> : (
        <>
          <div className="field">
            <Switch checked={s.enabled} onChange={(v) => setS({ ...s, enabled: v })}
              label="Раздавать подписку" />
          </div>
          <div className="field">
            <label>Имя подписки</label>
            <input value={s.name} onChange={(e) => setS({ ...s, name: e.target.value })} />
          </div>
          <div className="field">
            <label>Частота обновления (напр. 10m, 6h, 1d)</label>
            <input value={s.refresh} onChange={(e) => setS({ ...s, refresh: e.target.value })} />
          </div>
          <div className="field">
            <label>Порт раздачи</label>
            <input type="number" value={s.port}
              onChange={(e) => setS({ ...s, port: parseInt(e.target.value) || 0 })} />
          </div>
          <div className="field">
            <label>Подписка раздаётся на</label>
            <div className="uri uri-copy" title="Нажмите, чтобы скопировать"
              onClick={() => { copy(url); toast.push("Ссылка скопирована"); }}>{url}</div>
          </div>
          <div className="faint" style={{ lineHeight: 1.5, fontSize: ".8rem" }}>
            ⚠️ Если ваше приложение-клиент не поддерживает импорт подписок по HTTP,
            вам придётся настроить проксирование на адрес выше через nginx и
            установить TLS-сертификат.
          </div>
        </>
      )}
    </Modal>
  );
}
