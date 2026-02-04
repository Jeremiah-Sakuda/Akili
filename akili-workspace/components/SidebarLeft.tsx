import React from 'react';
import { AppState, DocumentFile } from '../types';

interface SidebarLeftProps {
  currentState: AppState;
  onStateChange: (state: AppState) => void;
  files: DocumentFile[];
  loading?: boolean;
  onSelectFile: (docId: string) => void;
}

const SidebarLeft: React.FC<SidebarLeftProps> = ({
  currentState,
  onStateChange,
  files,
  loading = false,
  onSelectFile,
}) => {
  const handleFileClick = (file: DocumentFile) => {
    onSelectFile(file.id);
    onStateChange(AppState.VERIFIED);
  };

  return (
    <aside className="w-[280px] bg-white border-r border-gray-200 flex flex-col z-20 shrink-0 h-full">
      <div className="p-4 border-b border-gray-100">
        <h2 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-1">Documents</h2>
        <div className="flex items-center justify-between">
          <span className="text-sm font-semibold text-slate-700">Project Files</span>
          <button
            type="button"
            onClick={() => onStateChange(AppState.UPLOAD)}
            className={`p-1 rounded transition-colors ${currentState === AppState.UPLOAD ? 'bg-primary text-white' : 'text-primary hover:bg-primary/10'}`}
          >
            <span className="material-symbols-outlined text-[18px]">add</span>
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-1">
        {loading ? (
          <div className="flex items-center justify-center py-8 text-slate-400 text-sm">Loading…</div>
        ) : files.length === 0 ? (
          <div className="text-center py-8 text-slate-400 text-sm">
            <p>No documents yet.</p>
            <p className="mt-1">Upload a PDF to get started.</p>
          </div>
        ) : (
          files.map((file) => (
            <div
              key={file.id}
              role="button"
              tabIndex={0}
              onClick={() => handleFileClick(file)}
              onKeyDown={(e) => e.key === 'Enter' && handleFileClick(file)}
              className={`
                group flex items-start gap-3 p-3 rounded-lg cursor-pointer transition-all border
                ${file.active
                  ? 'bg-primary/5 border-primary/20 relative overflow-hidden'
                  : 'hover:bg-gray-50 border-transparent hover:border-gray-200'}
              `}
            >
              {file.active && <div className="absolute left-0 top-0 bottom-0 w-1 bg-primary" />}
              <span
                className={`material-symbols-outlined mt-0.5 shrink-0 ${file.active ? 'text-primary' : 'text-slate-400 group-hover:text-slate-500'}`}
              >
                {file.icon}
              </span>
              <div className="flex flex-col min-w-0 flex-1">
                <p
                  className={`text-sm font-medium truncate leading-tight ${file.active ? 'text-primary font-semibold' : 'text-slate-600 group-hover:text-slate-900'}`}
                >
                  {file.name}
                </p>
                <p className={`text-xs mt-1 ${file.active ? 'text-primary/70' : 'text-slate-400'}`}>{file.meta}</p>
              </div>
            </div>
          ))
        )}
      </div>

      <div className="p-4 border-t border-gray-100 bg-gray-50/50">
        <div className="flex items-center gap-2 text-xs text-slate-500">
          <span className="material-symbols-outlined text-[16px]">cloud_done</span>
          <span>API connected</span>
        </div>
      </div>
    </aside>
  );
};

export default SidebarLeft;
