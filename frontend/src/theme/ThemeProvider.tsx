/** Theme context: applies tokens to :root, persists selection + custom themes. */

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { BUILTIN_THEMES, type Theme } from "./themes";
import { FALLBACKS } from "./tokens";

const LS_SELECTED = "fontaine.theme.selected";
const LS_CUSTOM = "fontaine.theme.custom";

interface ThemeCtx {
  themes: Theme[];          // builtin + custom
  current: Theme;
  select: (name: string) => void;
  addTheme: (theme: Theme) => void;       // add (or replace by name) a custom theme + select it
  removeTheme: (name: string) => void;
}

const Ctx = createContext<ThemeCtx | null>(null);

function applyTokens(theme: Theme): void {
  const root = document.documentElement;
  for (const key of Object.keys(FALLBACKS)) {
    root.style.setProperty(key, theme.tokens[key] ?? FALLBACKS[key]);
  }
}

function loadCustom(): Theme[] {
  try {
    const raw = localStorage.getItem(LS_CUSTOM);
    if (!raw) return [];
    const arr = JSON.parse(raw);
    return Array.isArray(arr) ? arr : [];
  } catch {
    return [];
  }
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [custom, setCustom] = useState<Theme[]>(loadCustom);
  const [selected, setSelected] = useState<string>(
    () => localStorage.getItem(LS_SELECTED) || BUILTIN_THEMES[0].name,
  );

  const themes = useMemo(() => [...BUILTIN_THEMES, ...custom], [custom]);
  const current = useMemo(
    () => themes.find((t) => t.name === selected) ?? BUILTIN_THEMES[0],
    [themes, selected],
  );

  useEffect(() => {
    applyTokens(current);
    localStorage.setItem(LS_SELECTED, current.name);
  }, [current]);

  useEffect(() => {
    localStorage.setItem(LS_CUSTOM, JSON.stringify(custom));
  }, [custom]);

  const select = useCallback((name: string) => setSelected(name), []);

  const addTheme = useCallback((theme: Theme) => {
    const t: Theme = { ...theme, builtin: false };
    setCustom((prev) => {
      const others = prev.filter((p) => p.name !== t.name);
      return [...others, t];
    });
    setSelected(t.name);
  }, []);

  const removeTheme = useCallback(
    (name: string) => {
      setCustom((prev) => prev.filter((p) => p.name !== name));
      if (selected === name) setSelected(BUILTIN_THEMES[0].name);
    },
    [selected],
  );

  const value: ThemeCtx = { themes, current, select, addTheme, removeTheme };
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useTheme(): ThemeCtx {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useTheme must be used within ThemeProvider");
  return ctx;
}
