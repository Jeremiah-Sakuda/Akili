import React from 'react';

const Header: React.FC = () => {
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

      <div className="flex items-center gap-3">
        <button type="button" className="flex items-center justify-center size-9 rounded-full hover:bg-gray-100 text-slate-500 transition-colors">
          <span className="material-symbols-outlined text-[20px]">settings</span>
        </button>
      </div>
    </header>
  );
};

export default Header;
