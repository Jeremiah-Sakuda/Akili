import React, { useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useTheme, type Theme } from '../contexts/ThemeContext';

const THEME_LABELS: Record<Theme, string> = {
  'dark': 'Dark',
  'very-dark': 'Very dark',
};

const Header: React.FC = () => {
  const { user, signOut } = useAuth();
  const { theme, setTheme, themes } = useTheme();
  const [menuOpen, setMenuOpen] = useState(false);
  const [themeMenuOpen, setThemeMenuOpen] = useState(false);

  return (
    <header className="h-12 bg-white dark:bg-[#0d1117] border-b border-gray-200 dark:border-[#30363d] flex items-center justify-between px-4 shrink-0 z-30 relative">
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2 text-primary cursor-pointer hover:opacity-80 transition-opacity">
          <div className="size-7 bg-primary flex items-center justify-center text-white">
            <svg fill="none" height="18" viewBox="0 0 24 24" width="18" xmlns="http://www.w3.org/2000/svg">
              <path d="M12 2L2 7L12 12L22 7L12 2Z" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" />
              <path d="M2 17L12 22L22 17" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" />
              <path d="M2 12L12 17L22 12" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" />
            </svg>
          </div>
          <h1 className="text-gray-900 dark:text-gray-100 text-base font-semibold tracking-tight">Akili</h1>
        </div>
        <div className="h-4 w-px bg-gray-300 dark:bg-[#30363d]" />
        <nav className="flex items-center text-xs hidden md:flex">
          <span className="text-gray-700 dark:text-gray-300 font-medium px-2 py-0.5 text-xs uppercase tracking-wider">Verification</span>
        </nav>
      </div>

      <div className="flex items-center gap-2 relative">
        <div className="relative">
          <button
            type="button"
            onClick={() => setThemeMenuOpen((o) => !o)}
            className="flex items-center justify-center gap-1.5 size-8 hover:bg-gray-100 dark:hover:bg-[#161b22] [.very-dark_&]:hover:bg-[#161b22] text-gray-600 dark:text-gray-400 rounded transition-colors"
            aria-label="Theme"
            aria-expanded={themeMenuOpen}
            aria-haspopup="listbox"
            title="Theme"
          >
            <span className="material-symbols-outlined text-[18px]">
              {theme === 'dark' ? 'dark_mode' : 'contrast'}
            </span>
            <span className="text-xs font-medium hidden sm:inline">{THEME_LABELS[theme]}</span>
          </button>
          {themeMenuOpen && (
            <>
              <div className="fixed inset-0 z-40" aria-hidden="true" onClick={() => setThemeMenuOpen(false)} />
              <ul
                role="listbox"
                className="absolute right-0 top-full mt-1 py-1 min-w-[120px] bg-white dark:bg-[#161b22] [.very-dark_&]:bg-[#0d1117] border border-gray-200 dark:border-[#30363d] rounded-lg shadow-lg z-50"
              >
                {themes.map((t) => (
                  <li key={t} role="option" aria-selected={theme === t}>
                    <button
                      type="button"
                      onClick={() => { setTheme(t); setThemeMenuOpen(false); }}
                      className={`w-full flex items-center gap-2 px-3 py-2 text-left text-sm transition-colors ${theme === t ? 'bg-primary/10 dark:bg-primary/20 text-primary font-medium' : 'text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-[#0d1117]'}`}
                    >
                      <span className="material-symbols-outlined text-[16px]">
                        {t === 'dark' ? 'dark_mode' : 'contrast'}
                      </span>
                      {THEME_LABELS[t]}
                    </button>
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
        {user && (
          <>
            <button
              type="button"
              onClick={() => setMenuOpen((o) => !o)}
              className="flex items-center gap-2 px-2 py-1 hover:bg-gray-100 dark:hover:bg-[#161b22] text-gray-700 dark:text-gray-300 text-sm transition-colors"
              aria-expanded={menuOpen}
              aria-haspopup="true"
            >
              {user.photoURL ? (
                <img src={user.photoURL} alt="" className="size-7" width={28} height={28} />
              ) : (
                <span className="size-7 bg-primary/10 flex items-center justify-center text-primary font-medium text-xs">
                  {user.email?.[0]?.toUpperCase() ?? '?'}
                </span>
              )}
              <span className="material-symbols-outlined text-[16px]">{menuOpen ? 'expand_less' : 'expand_more'}</span>
            </button>
            {menuOpen && (
              <>
                <div className="fixed inset-0 z-40" aria-hidden="true" onClick={() => setMenuOpen(false)} />
                <div className="absolute right-0 top-full mt-1 py-1 w-48 bg-white dark:bg-[#161b22] border border-gray-200 dark:border-[#30363d] z-50">
                  <div className="px-3 py-2 border-b border-gray-200 dark:border-[#30363d]">
                    <p className="text-xs text-gray-500 dark:text-gray-400 truncate font-mono">{user.email}</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => { setMenuOpen(false); signOut(); }}
                    className="w-full flex items-center gap-2 px-3 py-2 text-left text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-[#0d1117]"
                  >
                    <span className="material-symbols-outlined text-[16px]">logout</span>
                    Sign out
                  </button>
                </div>
              </>
            )}
          </>
        )}
        {!user && (
          <button type="button" className="flex items-center justify-center size-8 hover:bg-gray-100 dark:hover:bg-[#161b22] text-gray-500 dark:text-gray-400 transition-colors">
            <span className="material-symbols-outlined text-[18px]">settings</span>
          </button>
        )}
      </div>
    </header>
  );
};

export default Header;
