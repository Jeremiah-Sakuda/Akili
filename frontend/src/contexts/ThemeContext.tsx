import React, { createContext, useCallback, useContext, useEffect, useState } from 'react';

const STORAGE_KEY = 'akili-theme';

export type Theme = 'dark' | 'very-dark';

const THEMES: Theme[] = ['dark', 'very-dark'];

function getInitialTheme(): Theme {
  if (typeof window === 'undefined') return 'dark';
  const stored = localStorage.getItem(STORAGE_KEY) as Theme | null;
  if (stored === 'dark' || stored === 'very-dark') return stored;
  if (stored === 'light') return 'dark';
  if (window.matchMedia?.('(prefers-color-scheme: dark)').matches) return 'dark';
  return 'dark';
}

interface ThemeContextValue {
  theme: Theme;
  setTheme: (theme: Theme) => void;
  themes: Theme[];
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(getInitialTheme);

  useEffect(() => {
    const root = document.documentElement;
    root.setAttribute('data-theme', theme);
    root.classList.remove('dark', 'very-dark');
    root.classList.add('dark');
    if (theme === 'very-dark') root.classList.add('very-dark');
    localStorage.setItem(STORAGE_KEY, theme);
  }, [theme]);

  const setTheme = useCallback((value: Theme) => {
    setThemeState(value);
  }, []);

  return (
    <ThemeContext.Provider value={{ theme, setTheme, themes: THEMES }}>
      {children}
    </ThemeContext.Provider>
  );
}

// Context file: provider + hook is intentional; fast-refresh rule does not apply.
/* eslint-disable-next-line react-refresh/only-export-components */
export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error('useTheme must be used within ThemeProvider');
  return ctx;
}
