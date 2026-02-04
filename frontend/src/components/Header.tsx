import React, { useState } from 'react';
import { useAuth } from '../contexts/AuthContext';

const Header: React.FC = () => {
  const { user, signOut } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <header className="h-14 bg-white border-b border-gray-200 flex items-center justify-between px-4 shrink-0 z-30 shadow-sm relative">
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2 text-primary cursor-pointer hover:opacity-80 transition-opacity">
          <div className="size-8 bg-primary rounded-lg flex items-center justify-center text-white">
            <svg fill="none" height="20" viewBox="0 0 24 24" width="20" xmlns="http://www.w3.org/2000/svg">
              <path d="M12 2L2 7L12 12L22 7L12 2Z" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" />
              <path d="M2 17L12 22L22 17" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" />
              <path d="M2 12L12 17L22 12" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" />
            </svg>
          </div>
          <h1 className="text-slate-900 text-lg font-bold tracking-tight">Akili</h1>
        </div>
        <div className="h-6 w-px bg-gray-200 mx-2" />
        <nav className="flex items-center text-sm hidden md:flex">
          <span className="text-slate-900 font-semibold bg-gray-100 px-2 py-0.5 rounded text-xs uppercase tracking-wide">Verification</span>
        </nav>
      </div>

      <div className="flex items-center gap-3 relative">
        {user && (
          <>
            <button
              type="button"
              onClick={() => setMenuOpen((o) => !o)}
              className="flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-gray-100 text-slate-600 text-sm transition-colors"
              aria-expanded={menuOpen}
              aria-haspopup="true"
            >
              {user.photoURL ? (
                <img src={user.photoURL} alt="" className="size-8 rounded-full" width={32} height={32} />
              ) : (
                <span className="size-8 rounded-full bg-primary/10 flex items-center justify-center text-primary font-medium">
                  {user.email?.[0]?.toUpperCase() ?? '?'}
                </span>
              )}
              <span className="material-symbols-outlined text-[18px]">{menuOpen ? 'expand_less' : 'expand_more'}</span>
            </button>
            {menuOpen && (
              <>
                <div className="fixed inset-0 z-40" aria-hidden="true" onClick={() => setMenuOpen(false)} />
                <div className="absolute right-0 top-full mt-1 py-1 w-48 bg-white border border-gray-200 rounded-lg shadow-lg z-50">
                  <div className="px-3 py-2 border-b border-gray-100">
                    <p className="text-xs text-slate-500 truncate">{user.email}</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => { setMenuOpen(false); signOut(); }}
                    className="w-full flex items-center gap-2 px-3 py-2 text-left text-sm text-slate-700 hover:bg-gray-50"
                  >
                    <span className="material-symbols-outlined text-[18px]">logout</span>
                    Sign out
                  </button>
                </div>
              </>
            )}
          </>
        )}
        {!user && (
          <button type="button" className="flex items-center justify-center size-9 rounded-full hover:bg-gray-100 text-slate-500 transition-colors">
            <span className="material-symbols-outlined text-[20px]">settings</span>
          </button>
        )}
      </div>
    </header>
  );
};

export default Header;
