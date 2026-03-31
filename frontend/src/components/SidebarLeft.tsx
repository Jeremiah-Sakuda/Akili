import React, { useCallback, useEffect, useState } from 'react';
import { AppState, DocumentFile } from '../types';
import type { CanonicalResponse } from '../api';
import { getCanonical } from '../api';
import { useReveal } from '../hooks/useReveal';

type CanonicalTab = 'units' | 'bijections' | 'grids';

interface SidebarLeftProps {
  currentState: AppState;
  onStateChange: (state: AppState) => void;
  files: DocumentFile[];
  selectedDocId: string | null;
  loading?: boolean;
  onSelectFile: (docId: string) => void;
  onDeleteDocument?: (docId: string) => void;
}

function SkeletonRow() {
  return (
    <div className="flex items-start gap-2.5 p-2.5">
      <div className="skeleton w-5 h-5 shrink-0 rounded" />
      <div className="flex-1 space-y-1.5">
        <div className="skeleton h-3.5 w-3/4 rounded" />
        <div className="skeleton h-2.5 w-1/2 rounded" />
      </div>
    </div>
  );
}

const SidebarLeft: React.FC<SidebarLeftProps> = ({
  currentState,
  onStateChange,
  files,
  selectedDocId,
  loading = false,
  onSelectFile,
  onDeleteDocument,
}) => {
  const [canonicalTab, setCanonicalTab] = useState<CanonicalTab>('units');
  const [canonical, setCanonical] = useState<CanonicalResponse | null>(null);
  const [canonicalLoading, setCanonicalLoading] = useState(false);
  const { revealClass } = useReveal('reveal-left', 80);

  const fetchCanonical = useCallback(async (docId: string) => {
    setCanonicalLoading(true);
    try {
      const data = await getCanonical(docId);
      setCanonical(data);
    } catch {
      setCanonical(null);
    } finally {
      setCanonicalLoading(false);
    }
  }, []);

  useEffect(() => {
    if (selectedDocId) {
      fetchCanonical(selectedDocId);
    } else {
      setCanonical(null);
    }
  }, [selectedDocId, fetchCanonical]);

  const handleFileClick = (file: DocumentFile) => {
    onSelectFile(file.id);
    onStateChange(AppState.VERIFIED);
  };

  return (
    <aside className={`sidebar-left w-[280px] bg-white dark:bg-[#0d1117] border-r border-gray-200 dark:border-[#30363d] flex flex-col z-20 shrink-0 h-full ${revealClass}`}>
      <div className="p-3 border-b border-gray-200 dark:border-[#30363d]">
        <h2 className="text-[10px] font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-1.5">Documents</h2>
        <div className="flex items-center justify-between">
          <span className="font-heading text-sm text-gray-900 dark:text-gray-100">Project Files</span>
          <button
            type="button"
            onClick={() => onStateChange(AppState.UPLOAD)}
            className={`p-1.5 transition-colors ${currentState === AppState.UPLOAD ? 'bg-primary text-white' : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-[#161b22]'}`}
            aria-label="Upload new document"
            title="Upload new document"
          >
            <span className="material-symbols-outlined text-[16px]">add</span>
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-2 space-y-1 min-h-0 stagger">
        {loading ? (
          <>
            <SkeletonRow />
            <SkeletonRow />
            <SkeletonRow />
          </>
        ) : files.length === 0 ? (
          <div className="text-center py-8 text-gray-500 dark:text-gray-400 text-sm reveal visible">
            <p>No documents yet.</p>
            <p className="mt-1">Upload a PDF to get started.</p>
          </div>
        ) : (
          files.map((file, i) => (
            <div
              key={file.id}
              role="button"
              tabIndex={0}
              onClick={() => handleFileClick(file)}
              onKeyDown={(e) => e.key === 'Enter' && handleFileClick(file)}
              className={`
                reveal visible group flex items-start gap-2.5 p-2.5 cursor-pointer transition-all border
                ${file.active
                  ? 'bg-primary/5 dark:bg-primary/10 border-l-2 border-primary relative'
                  : 'hover:bg-gray-50 dark:hover:bg-[#161b22] border-transparent hover:border-gray-200 dark:hover:border-[#30363d]'}
              `}
              style={{ transitionDelay: `${i * 0.04}s` }}
            >
              <span
                className={`material-symbols-outlined mt-0.5 shrink-0 text-[18px] ${file.active ? 'text-primary' : 'text-gray-500 dark:text-gray-400 group-hover:text-gray-700 dark:group-hover:text-gray-300'}`}
              >
                {file.icon}
              </span>
              <div className="flex flex-col min-w-0 flex-1">
                <p
                  className={`text-sm font-medium truncate leading-tight ${file.active ? 'text-primary font-semibold' : 'text-gray-700 dark:text-gray-300 group-hover:text-gray-900 dark:group-hover:text-gray-100'}`}
                >
                  {file.name}
                </p>
                <p className={`text-xs mt-0.5 font-mono ${file.active ? 'text-primary/80 dark:text-primary/70' : 'text-gray-500 dark:text-gray-500'}`}>{file.meta}</p>
              </div>
              {onDeleteDocument && (
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    if (window.confirm(`Delete "${file.name}"? This cannot be undone.`)) {
                      onDeleteDocument(file.id);
                    }
                  }}
                  className="p-1 shrink-0 rounded text-gray-400 hover:text-red-600 dark:hover:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 opacity-0 group-hover:opacity-100 transition-opacity"
                  title="Delete document"
                  aria-label={`Delete ${file.name}`}
                >
                  <span className="material-symbols-outlined text-[18px]">delete</span>
                </button>
              )}
            </div>
          ))
        )}
      </div>

      {selectedDocId && (
        <div className="border-t border-gray-200 dark:border-[#30363d] flex flex-col min-h-0 shrink-0" style={{ maxHeight: '40%' }}>
          <div className="p-1.5 border-b border-gray-200 dark:border-[#30363d] flex gap-1 bg-gray-50 dark:bg-[#161b22]" role="tablist" aria-label="Canonical object types">
            {(['units', 'bijections', 'grids'] as const).map((tab) => (
              <button
                key={tab}
                type="button"
                role="tab"
                aria-selected={canonicalTab === tab}
                onClick={() => setCanonicalTab(tab)}
                className={`px-2 py-1 text-xs font-medium capitalize transition-colors ${canonicalTab === tab ? 'bg-primary text-white' : 'text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-[#0d1117]'}`}
              >
                {tab}
              </button>
            ))}
          </div>
          <div className="flex-1 overflow-y-auto p-2 text-xs font-mono min-h-0 stagger">
            {canonicalLoading ? (
              <div className="space-y-1.5">
                {[0, 1, 2].map((i) => (
                  <div key={i} className="p-2 space-y-1">
                    <div className="skeleton h-3 w-full rounded" />
                    <div className="skeleton h-2.5 w-2/3 rounded" />
                  </div>
                ))}
              </div>
            ) : canonical ? (
              canonicalTab === 'units' ? (
                <ul className="space-y-1.5">
                  {canonical.units.length === 0 ? (
                    <li className="text-gray-500 dark:text-gray-400">No units</li>
                  ) : (
                    canonical.units.map((u, i) => (
                      <li key={`unit-${i}`} className="reveal visible p-2 bg-gray-50 dark:bg-[#161b22] border border-gray-200 dark:border-[#30363d]" style={{ transitionDelay: `${i * 0.03}s` }}>
                        <span className="text-gray-600 dark:text-gray-400">{u.id}</span> {u.label ?? ''} {String(u.value)}{u.unit_of_measure ? ` ${u.unit_of_measure}` : ''}
                        <br />
                        <span className="text-gray-500 dark:text-gray-500">p{u.page} (x:{u.origin.x.toFixed(2)}, y:{u.origin.y.toFixed(2)})</span>
                      </li>
                    ))
                  )}
                </ul>
              ) : canonicalTab === 'bijections' ? (
                <ul className="space-y-1.5">
                  {canonical.bijections.length === 0 ? (
                    <li className="text-gray-500 dark:text-gray-400">No bijections</li>
                  ) : (
                    canonical.bijections.map((b, i) => (
                      <li key={`bijection-${i}`} className="reveal visible p-2 bg-gray-50 dark:bg-[#161b22] border border-gray-200 dark:border-[#30363d]" style={{ transitionDelay: `${i * 0.03}s` }}>
                        <span className="text-gray-600 dark:text-gray-400">{b.id}</span> {Object.entries(b.mapping).slice(0, 3).map(([k, v]) => `${k}→${v}`).join(', ')}
                        {Object.keys(b.mapping).length > 3 ? '…' : ''}
                        <br />
                        <span className="text-gray-500 dark:text-gray-500">p{b.page} (x:{b.origin.x.toFixed(2)}, y:{b.origin.y.toFixed(2)})</span>
                      </li>
                    ))
                  )}
                </ul>
              ) : (
                <ul className="space-y-1.5">
                  {canonical.grids.length === 0 ? (
                    <li className="text-gray-500 dark:text-gray-400">No grids</li>
                  ) : (
                    canonical.grids.map((g, i) => (
                      <li key={`grid-${i}`} className="reveal visible p-2 bg-gray-50 dark:bg-[#161b22] border border-gray-200 dark:border-[#30363d]" style={{ transitionDelay: `${i * 0.03}s` }}>
                        <span className="text-gray-600 dark:text-gray-400">{g.id}</span> {g.rows}×{g.cols} ({g.cells_count} cells)
                        <br />
                        <span className="text-gray-500 dark:text-gray-500">p{g.page} (x:{g.origin.x.toFixed(2)}, y:{g.origin.y.toFixed(2)})</span>
                      </li>
                    ))
                  )}
                </ul>
              )
            ) : (
              <div className="py-4 text-center text-gray-500 dark:text-gray-400">Select a document</div>
            )}
          </div>
        </div>
      )}

      <div className="p-3 border-t border-gray-200 dark:border-[#30363d] bg-gray-50 dark:bg-[#161b22]">
        <div className="flex items-center gap-2 text-xs text-gray-600 dark:text-gray-400">
          <span className="material-symbols-outlined text-[14px]">cloud_done</span>
          <span className="font-mono">API connected</span>
        </div>
      </div>
    </aside>
  );
};

export default SidebarLeft;
