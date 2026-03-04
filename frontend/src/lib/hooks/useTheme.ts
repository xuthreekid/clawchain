"use client";

import { useState, useCallback, useEffect } from "react";

export type ThemeMode = "system" | "light" | "dark";
export type EffectiveTheme = "light" | "dark";

const STORAGE_KEY = "clawchain-theme";

export function useTheme() {
  const [theme, setThemeState] = useState<ThemeMode>("system");
  const [effectiveTheme, setEffectiveTheme] = useState<EffectiveTheme>("light");

  const computeEffective = useCallback((mode: ThemeMode): EffectiveTheme => {
    if (mode === "dark") return "dark";
    if (mode === "light") return "light";
    if (typeof window !== "undefined" && window.matchMedia?.("(prefers-color-scheme: dark)")?.matches) return "dark";
    return "light";
  }, []);

  const applyTheme = useCallback((mode: ThemeMode) => {
    if (typeof document !== "undefined") {
      document.documentElement.dataset.theme = mode;
    }
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const stored = window.localStorage.getItem(STORAGE_KEY) as ThemeMode | null;
    const initial: ThemeMode = stored || "system";
    setThemeState(initial);
    applyTheme(initial);
    setEffectiveTheme(computeEffective(initial));
  }, [applyTheme, computeEffective]);

  useEffect(() => {
    setEffectiveTheme(computeEffective(theme));
    if (theme === "system" && typeof window !== "undefined") {
      const mql = window.matchMedia?.("(prefers-color-scheme: dark)");
      const handler = () => setEffectiveTheme(computeEffective("system"));
      mql?.addEventListener?.("change", handler);
      return () => mql?.removeEventListener?.("change", handler);
    }
  }, [theme, computeEffective]);

  const setTheme = useCallback((mode: ThemeMode) => {
    setThemeState(mode);
    if (typeof window !== "undefined") {
      window.localStorage.setItem(STORAGE_KEY, mode);
    }
    applyTheme(mode);
  }, [applyTheme]);

  return { theme, effectiveTheme, setTheme };
}
