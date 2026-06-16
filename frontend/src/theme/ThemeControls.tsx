/** Theme switcher + download-template + upload-theme controls (header widget). */

import { useRef, useState } from "react";
import { useTheme } from "./ThemeProvider";
import { buildTemplate, downloadText, parseThemeFile } from "./themeIO";

export function ThemeControls({ onToast }: { onToast?: (msg: string, ok?: boolean) => void }) {
  const { themes, current, select, addTheme, removeTheme } = useTheme();
  const [open, setOpen] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const toast = (m: string, ok = true) => onToast?.(m, ok);

  const handleDownload = () => {
    downloadText(`fontaine-theme-${current.name}.json`, buildTemplate(current));
    toast("Шаблон темы скачан");
  };

  const handleUpload = async (file: File) => {
    try {
      const parsed = parseThemeFile(await file.text());
      addTheme(parsed.theme);
      let msg = `Тема «${parsed.theme.name}» добавлена`;
      if (parsed.unknownKeys.length) msg += ` (пропущено неизвестных ключей: ${parsed.unknownKeys.length})`;
      if (parsed.missingKeys.length) msg += ` (заполнено по умолчанию: ${parsed.missingKeys.length})`;
      toast(msg);
    } catch (e) {
      toast(e instanceof Error ? e.message : "Не удалось загрузить тему", false);
    }
  };

  return (
    <div className="theme-controls">
      <button className="btn btn-ghost" onClick={() => setOpen((o) => !o)} title="Темы">
        🎨 {current.name}
      </button>
      {open && (
        <>
          <div className="dropdown-backdrop" onClick={() => setOpen(false)} />
          <div className="dropdown">
            <div className="dropdown-title">Тема оформления</div>
            {themes.map((t) => (
              <div
                key={t.name}
                className={`dropdown-item ${t.name === current.name ? "active" : ""}`}
                onClick={() => { select(t.name); setOpen(false); }}
              >
                <span
                  className="swatch"
                  style={{
                    background: `linear-gradient(135deg, ${t.tokens["--ft-surface"]} 0 50%, ${t.tokens["--ft-accent"]} 50% 100%)`,
                  }}
                />
                <span className="dropdown-item-label">{t.name}</span>
                {!t.builtin && (
                  <button
                    className="dropdown-remove"
                    title="Удалить тему"
                    onClick={(e) => { e.stopPropagation(); removeTheme(t.name); }}
                  >
                    ✕
                  </button>
                )}
              </div>
            ))}
            <div className="dropdown-sep" />
            <div className="dropdown-item" onClick={handleDownload}>⬇ Скачать шаблон темы</div>
            <div className="dropdown-item" onClick={() => fileRef.current?.click()}>⬆ Загрузить тему…</div>
          </div>
        </>
      )}
      <input
        ref={fileRef}
        type="file"
        accept=".json,application/json"
        style={{ display: "none" }}
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) handleUpload(f);
          e.target.value = "";
        }}
      />
    </div>
  );
}
