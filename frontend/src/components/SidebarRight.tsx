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
  onStateChange: _onStateChange,
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
      const result = await query(selectedDocId, question.trim(), { includeFormattedAnswer: true });
      onQueryResult(result);
    } catch {
      onQueryResult({ status: 'refuse', reason: 'Query failed. Is the API running?' });
    } finally {
      setQueryLoading(false);
    }
  };

  if (isUpload) {
    return (
      <aside className="w-[400px] bg-white dark:bg-[#0d1117] border-l border-gray-200 dark:border-[#30363d] flex flex-col z-20 shrink-0 h-full">
        <div className="p-4 border-b border-gray-200 dark:border-[#30363d] flex items-center justify-between bg-white dark:bg-[#0d1117]">
          <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100">Processing Queue</h2>
        </div>
        <div className="flex-1 flex flex-col items-center justify-center p-8 space-y-4">
          <div className="size-12 bg-gray-100 dark:bg-[#161b22] flex items-center justify-center">
            <span className="material-symbols-outlined text-gray-400 dark:text-gray-500 text-[24px]">pending_actions</span>
          </div>
          <div className="text-center space-y-1 max-w-[240px]">
            <h3 className="text-gray-900 dark:text-gray-100 font-medium text-sm">Waiting for Documents</h3>
            <p className="text-xs text-gray-600 dark:text-gray-400 leading-relaxed">
              Upload a PDF to start verification. After ingest, you can ask questions here.
            </p>
          </div>
        </div>
        <div className="p-3 border-t border-gray-200 dark:border-[#30363d] bg-gray-50 dark:bg-[#161b22] text-center">
          <p className="text-xs text-gray-500 dark:text-gray-500 font-mono">Select a document and ask a question</p>
        </div>
      </aside>
    );
  }

  return (
    <aside className="w-[400px] bg-white dark:bg-[#0d1117] border-l border-gray-200 dark:border-[#30363d] flex flex-col z-20 shrink-0 h-full">
      <div className="p-4 border-b border-gray-200 dark:border-[#30363d] flex items-center justify-between bg-white dark:bg-[#0d1117]">
        <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100">Verification Query</h2>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {documents.length === 0 ? (
          <p className="text-sm text-gray-600 dark:text-gray-400">Upload a document first to run queries.</p>
        ) : (
          <>
            <div className="space-y-2">
              <label className="text-[10px] font-semibold uppercase tracking-wider text-gray-600 dark:text-gray-400">Document</label>
              <select
                className="w-full p-2.5 bg-white dark:bg-[#161b22] border border-gray-300 dark:border-[#30363d] text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-1 focus:ring-primary"
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

            <div className="space-y-2">
              <label className="text-[10px] font-semibold uppercase tracking-wider text-gray-600 dark:text-gray-400">Question</label>
              <textarea
                className="w-full min-h-[100px] p-3 bg-white dark:bg-[#161b22] border border-gray-300 dark:border-[#30363d] text-gray-900 dark:text-gray-100 text-sm resize-y focus:outline-none focus:ring-1 focus:ring-primary font-mono"
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
              className="w-full flex items-center justify-center gap-2 bg-primary hover:bg-[#0052a3] disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium py-2.5 px-4 transition-colors"
            >
              <span className="material-symbols-outlined text-[18px]">search_check</span>
              {queryLoading ? 'Verifying…' : 'Verify'}
            </button>

            <div className="h-px bg-gray-200 dark:bg-[#30363d] w-full" />

            <div className="space-y-2">
              <label className="text-[10px] font-semibold uppercase tracking-wider text-gray-600 dark:text-gray-400">Result</label>

              {queryResult === null && !queryLoading && (
                <p className="text-sm text-gray-500 dark:text-gray-500">Ask a question and click Verify.</p>
              )}

              {queryResult !== null && isRefuse(queryResult) && (
                <div className="border border-amber-300 dark:border-amber-700 bg-amber-50 dark:bg-amber-900/20">
                  <div className="px-4 py-2.5 border-b border-amber-200 dark:border-amber-800 bg-amber-100 dark:bg-amber-900/30 flex items-center gap-2">
                    <span className="material-symbols-outlined text-amber-700 dark:text-amber-400 text-[16px]">block</span>
                    <span className="text-amber-800 dark:text-amber-300 font-semibold text-xs tracking-wide uppercase">REFUSED</span>
                  </div>
                  <div className="p-4">
                    <p className="text-amber-900 dark:text-amber-200 text-sm leading-relaxed">{queryResult.reason}</p>
                  </div>
                </div>
              )}

              {queryResult !== null && !isRefuse(queryResult) && (
                <div className="border border-emerald-300 dark:border-emerald-700 bg-emerald-50 dark:bg-emerald-900/20">
                  <div className="px-4 py-2.5 border-b border-emerald-200 dark:border-emerald-800 bg-emerald-100 dark:bg-emerald-900/30 flex items-center gap-2">
                    <span className="material-symbols-outlined text-emerald-700 dark:text-emerald-400 text-[16px]">
                      check_circle
                    </span>
                    <span className="text-emerald-800 dark:text-emerald-300 font-semibold text-xs tracking-wide uppercase">VERIFIED</span>
                  </div>
                  <div className="p-4">
                    <p className="text-gray-900 dark:text-gray-100 text-sm leading-relaxed">
                      {queryResult.formatted_answer ?? queryResult.answer}
                    </p>
                    {(queryResult.formatted_answer != null && queryResult.formatted_answer !== queryResult.answer) && (
                      <p className="mt-2 text-xs text-gray-500 dark:text-gray-400 font-mono">
                        Raw: {queryResult.answer}
                      </p>
                    )}
                    {queryResult.proof?.length > 0 && (
                      <div className="mt-4 pt-4 border-t border-emerald-200 dark:border-emerald-800">
                        <label className="text-[10px] font-semibold uppercase tracking-wider text-emerald-700 dark:text-emerald-400 mb-2 block">
                          Proof (coordinates)
                        </label>
                        <div className="bg-white dark:bg-[#0d1117] border border-emerald-200 dark:border-emerald-800 p-3 space-y-1">
                          {queryResult.proof.map((p, i) => (
                            <p key={i} className="text-xs font-mono text-gray-700 dark:text-gray-300">
                              (x: {p.x}, y: {p.y})
                              {p.source_id != null && ` · ${p.source_type ?? ''} ${p.source_id}`}
                            </p>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                  <div className="px-3 py-2 bg-emerald-100 dark:bg-emerald-900/30 border-t border-emerald-200 dark:border-emerald-800">
                    <button
                      type="button"
                      onClick={() => onShowProof(queryResult.proof ?? null)}
                      className="w-full flex items-center justify-center gap-2 bg-white dark:bg-[#0d1117] hover:bg-emerald-50 dark:hover:bg-emerald-900/40 text-emerald-700 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800 font-medium py-2 px-3 text-xs transition-colors"
                    >
                      <span className="material-symbols-outlined text-[14px]">visibility</span>
                      Show proof on document
                    </button>
                  </div>
                </div>
              )}
            </div>
          </>
        )}
      </div>

      <div className="p-3 border-t border-gray-200 dark:border-[#30363d] bg-gray-50 dark:bg-[#161b22] text-center">
        <p className="text-xs text-gray-500 dark:text-gray-500 font-mono">Akili • Coordinate-grounded verification</p>
      </div>
    </aside>
  );
};

export default SidebarRight;
