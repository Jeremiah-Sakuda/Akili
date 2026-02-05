import React, { useState } from 'react';
import { AppState } from '../types';
import type { DocumentSummary, ProofPoint, QueryResponse } from '../api';
import { query, isRefuse } from '../api';

interface SidebarRightProps {
  currentState: AppState;
  onStateChange: (state: AppState) => void;
  selectedDocId: string | null;
  documents: DocumentSummary[];
  queryResult: QueryResponse | null;
  onQueryResult: (result: QueryResponse) => void;
  onSelectDoc: (docId: string) => void;
  onShowProof: (proof: ProofPoint[] | null) => void;
  queryLoading: boolean;
  setQueryLoading: (v: boolean) => void;
}

const SidebarRight: React.FC<SidebarRightProps> = ({
  currentState,
  onStateChange,
  selectedDocId,
  documents,
  queryResult,
  onQueryResult,
  onSelectDoc,
  onShowProof,
  queryLoading,
  setQueryLoading,
}) => {
  const [question, setQuestion] = useState('');
  const isUpload = currentState === AppState.UPLOAD;

  const handleVerify = async () => {
    if (!selectedDocId?.trim() || !question.trim()) return;
    setQueryLoading(true);
    try {
      const result = await query(selectedDocId, question.trim());
      onQueryResult(result);
    } catch {
      onQueryResult({ status: 'refuse', reason: 'Query failed. Is the API running?' });
    } finally {
      setQueryLoading(false);
    }
  };

  if (isUpload) {
    return (
      <aside className="w-[400px] bg-white border-l border-gray-200 flex flex-col z-20 shadow-soft shrink-0 h-full">
        <div className="p-6 border-b border-gray-100 flex items-center justify-between bg-white">
          <h2 className="text-base font-bold text-slate-800">Processing Queue</h2>
        </div>
        <div className="flex-1 flex flex-col items-center justify-center p-8 space-y-4">
          <div className="size-16 rounded-full bg-slate-50 flex items-center justify-center">
            <span className="material-symbols-outlined text-slate-300 text-[32px]">pending_actions</span>
          </div>
          <div className="text-center space-y-1 max-w-[240px]">
            <h3 className="text-slate-900 font-medium">Waiting for Documents</h3>
            <p className="text-sm text-slate-500 leading-relaxed">
              Upload a PDF to start verification. After ingest, you can ask questions here.
            </p>
          </div>
        </div>
        <div className="p-4 border-t border-gray-100 bg-gray-50 text-center">
          <p className="text-xs text-slate-400 font-mono">Select a document and ask a question</p>
        </div>
      </aside>
    );
  }

  return (
    <aside className="w-[400px] bg-white border-l border-gray-200 flex flex-col z-20 shadow-soft shrink-0 h-full">
      <div className="p-6 border-b border-gray-100 flex items-center justify-between bg-white">
        <h2 className="text-base font-bold text-slate-800">Verification Query</h2>
      </div>

      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {documents.length === 0 ? (
          <p className="text-sm text-slate-500">Upload a document first to run queries.</p>
        ) : (
          <>
            <div className="space-y-3">
              <label className="text-xs font-bold uppercase tracking-wider text-slate-500">Document</label>
              <select
                className="w-full p-3 bg-slate-50 border border-slate-200 rounded-lg text-sm text-slate-800"
                value={selectedDocId ?? ''}
                onChange={(e) => onSelectDoc(e.target.value)}
              >
                {documents.map((d) => (
                  <option key={d.doc_id} value={d.doc_id}>
                    {d.filename || d.doc_id}
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-3">
              <label className="text-xs font-bold uppercase tracking-wider text-slate-500">Question</label>
              <textarea
                className="w-full min-h-[80px] p-4 bg-slate-50 border border-slate-200 rounded-lg text-slate-800 text-base font-medium shadow-sm resize-y"
                placeholder="e.g. What is pin 5? Maximum voltage?"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                disabled={queryLoading}
              />
            </div>

            <button
              type="button"
              onClick={handleVerify}
              disabled={!selectedDocId || !question.trim() || queryLoading}
              className="w-full flex items-center justify-center gap-2 bg-primary hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold py-3 px-4 rounded-lg shadow-sm transition-all active:scale-[0.98]"
            >
              <span className="material-symbols-outlined text-[20px]">search_check</span>
              {queryLoading ? 'Verifying…' : 'Verify'}
            </button>

            <div className="h-px bg-gray-100 w-full" />

            <div className="space-y-3">
              <label className="text-xs font-bold uppercase tracking-wider text-slate-500">Result</label>

              {queryResult === null && !queryLoading && (
                <p className="text-sm text-slate-400">Ask a question and click Verify.</p>
              )}

              {queryResult !== null && isRefuse(queryResult) && (
                <div className="rounded-xl border border-amber-200 bg-amber-50 overflow-hidden shadow-sm">
                  <div className="px-5 py-3 border-b border-amber-100 bg-amber-100/50 flex items-center gap-3">
                    <div className="size-6 rounded-full bg-amber-200 flex items-center justify-center shrink-0">
                      <span className="material-symbols-outlined text-amber-700 text-[16px] font-bold">block</span>
                    </div>
                    <span className="text-amber-800 font-bold text-sm tracking-wide">REFUSED</span>
                  </div>
                  <div className="p-5">
                    <p className="text-amber-900 text-sm leading-relaxed font-medium">{queryResult.reason}</p>
                  </div>
                </div>
              )}

              {queryResult !== null && !isRefuse(queryResult) && (
                <div className="rounded-xl border border-emerald-200 bg-emerald-50/50 overflow-hidden shadow-sm">
                  <div className="px-5 py-3 border-b border-emerald-100 bg-emerald-100/50 flex items-center gap-3">
                    <div className="size-6 rounded-full bg-emerald-200 flex items-center justify-center shrink-0">
                      <span className="material-symbols-outlined text-emerald-700 text-[16px] font-bold">
                        check_circle
                      </span>
                    </div>
                    <span className="text-emerald-800 font-bold text-sm tracking-wide">VERIFIED</span>
                  </div>
                  <div className="p-5">
                    <p className="text-slate-800 text-sm leading-relaxed font-medium">{queryResult.answer}</p>
                    {queryResult.proof?.length > 0 && (
                      <div className="mt-4 pt-4 border-t border-emerald-200/60">
                        <label className="text-[10px] font-bold uppercase tracking-wider text-emerald-700/70 mb-2 block">
                          Proof (coordinates)
                        </label>
                        <div className="bg-white border border-emerald-200/60 rounded p-3 space-y-1">
                          {queryResult.proof.map((p, i) => (
                            <p key={i} className="text-xs font-mono text-slate-600">
                              (x: {p.x}, y: {p.y})
                              {p.source_id != null && ` · ${p.source_type ?? ''} ${p.source_id}`}
                            </p>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                  <div className="px-3 py-2 bg-emerald-100/30 flex justify-end gap-2">
                    <button
                      type="button"
                      onClick={() => onShowProof(queryResult.proof ?? null)}
                      className="w-full flex items-center justify-center gap-2 bg-white hover:bg-emerald-50 text-emerald-700 border border-emerald-200 font-semibold py-2 px-3 rounded shadow-sm transition-all text-xs"
                    >
                      <span className="material-symbols-outlined text-[16px]">visibility</span>
                      Show proof on document
                    </button>
                  </div>
                </div>
              )}
            </div>
          </>
        )}
      </div>

      <div className="p-4 border-t border-gray-100 bg-gray-50 text-center">
        <p className="text-xs text-slate-400">Akili • Coordinate-grounded verification</p>
      </div>
    </aside>
  );
};

export default SidebarRight;
