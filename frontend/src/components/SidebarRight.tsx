import React, { useEffect, useRef, useState } from 'react';
import { AppState } from '../types';
import type { DocumentSummary, ProofPoint, QueryResponse, UsageSummary } from '../api';
import { isRefuse, getUsage } from '../api';
import type { ChatMessage } from '../api';
import { useReveal } from '../hooks/useReveal';

interface SidebarRightProps {
  currentState: AppState;
  onStateChange: (state: AppState) => void;
  selectedDocId: string | null;
  documents: DocumentSummary[];
  messages: ChatMessage[];
  onSendQuestion: (question: string) => void;
  onSelectDoc: (docId: string) => void;
  onShowProof: (proof: ProofPoint[] | null) => void;
  queryLoading: boolean;
}

function TypingIndicator() {
  return (
    <div className="flex justify-start">
      <div className="rounded-lg px-4 py-3 bg-gray-100 dark:bg-[#161b22] text-gray-500 dark:text-gray-400">
        <div className="flex items-center gap-2">
          <span className="material-symbols-outlined text-[14px] text-primary animate-spin" style={{ animationDuration: '2s' }}>progress_activity</span>
          <span className="text-sm">Verifying</span>
          <div className="typing-dots">
            <span /><span /><span />
          </div>
        </div>
      </div>
    </div>
  );
}

const MAX_QUESTION_LENGTH = 2000;

const SidebarRight: React.FC<SidebarRightProps> = ({
  currentState,
  // onStateChange not used in this component currently
  onStateChange: _onStateChange,
  selectedDocId,
  documents,
  messages,
  onSendQuestion,
  onSelectDoc,
  onShowProof,
  queryLoading,
}) => {
  const [question, setQuestion] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const isUpload = currentState === AppState.UPLOAD;
  const { revealClass } = useReveal('reveal', 120);
  const [usage, setUsage] = useState<UsageSummary | null>(null);

  useEffect(() => {
    getUsage().then(setUsage).catch(() => {});
  }, [messages.length]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleVerify = () => {
    if (!question.trim()) return;
    onSendQuestion(question.trim());
    setQuestion('');
  };

  const renderAssistantBlock = (msg: ChatMessage, index: number) => {
    if (msg.role !== 'assistant' || !msg.response) {
      return <p className="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap">{msg.text}</p>;
    }
    const res = msg.response as QueryResponse;
    if (isRefuse(res)) {
      return (
        <div className="reveal-scale visible border border-amber-300 dark:border-amber-700 bg-amber-50 dark:bg-amber-900/20 rounded-lg overflow-hidden" style={{ transitionDelay: `${index * 0.05}s` }}>
          <div className="badge-refused px-3 py-2 border-b border-amber-200 dark:border-amber-800 bg-amber-100 dark:bg-amber-900/30 flex items-center gap-2">
            <span className="material-symbols-outlined text-amber-700 dark:text-amber-400 text-[14px]">block</span>
            <span className="text-amber-800 dark:text-amber-300 font-heading text-xs tracking-wide uppercase">REFUSED</span>
          </div>
          <div className="p-3">
            <p className="text-amber-900 dark:text-amber-200 text-sm leading-relaxed">{res.reason}</p>
          </div>
        </div>
      );
    }
    const isRephrased = res.formatting_source === 'gemini_rephrase' && res.formatted_answer;
    const answer = isRephrased ? res.formatted_answer! : res.answer;
    const tier = res.confidence_tier ?? 'verified';
    const isReview = tier === 'review';

    const borderColor = isReview
      ? 'border-yellow-300 dark:border-yellow-700'
      : 'border-emerald-300 dark:border-emerald-700';
    const bgColor = isReview
      ? 'bg-yellow-50 dark:bg-yellow-900/20'
      : 'bg-emerald-50 dark:bg-emerald-900/20';
    const headerBg = isReview
      ? 'bg-yellow-100 dark:bg-yellow-900/30 border-yellow-200 dark:border-yellow-800'
      : 'bg-emerald-100 dark:bg-emerald-900/30 border-emerald-200 dark:border-emerald-800';
    const iconColor = isReview
      ? 'text-yellow-700 dark:text-yellow-400'
      : 'text-emerald-700 dark:text-emerald-400';
    const labelColor = isReview
      ? 'text-yellow-800 dark:text-yellow-300'
      : 'text-emerald-800 dark:text-emerald-300';
    const badgeAnimation = isReview ? 'badge-review' : 'badge-verified';

    return (
      <div className={`reveal-scale visible border ${borderColor} ${bgColor} rounded-lg overflow-hidden`} style={{ transitionDelay: `${index * 0.05}s` }}>
        <div className={`${badgeAnimation} px-3 py-2 border-b ${headerBg} flex items-center gap-2`}>
          <span className={`material-symbols-outlined ${iconColor} text-[14px]`}>
            {isReview ? 'help' : 'check_circle'}
          </span>
          <span className={`${labelColor} font-heading text-xs tracking-wide uppercase`}>
            {isReview ? 'REVIEW' : 'VERIFIED'}
          </span>
          {res.confidence?.overall != null && (
            <span className="text-[10px] font-mono text-gray-500 dark:text-gray-400">
              {Math.round(res.confidence.overall * 100)}%
            </span>
          )}
          {isRephrased && (
            <span className="ml-auto text-[10px] font-medium text-gray-500 dark:text-gray-400 bg-gray-200 dark:bg-gray-700 px-1.5 py-0.5 rounded">
              AI-rephrased
            </span>
          )}
        </div>
        <div className="p-3">
          <p className="text-gray-900 dark:text-gray-100 text-sm leading-relaxed">{answer}</p>
          {res.proof?.length > 0 && (
            <div className={`mt-3 pt-3 border-t ${isReview ? 'border-yellow-200 dark:border-yellow-800' : 'border-emerald-200 dark:border-emerald-800'}`}>
              <button
                type="button"
                onClick={() => onShowProof(res.proof ?? null)}
                className="w-full flex items-center justify-center gap-2 bg-white dark:bg-[#0d1117] hover:bg-emerald-50 dark:hover:bg-emerald-900/40 text-emerald-700 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800 font-medium py-1.5 px-2 text-xs transition-all hover:shadow-sm rounded"
              >
                <span className="material-symbols-outlined text-[12px]">visibility</span>
                Show proof on document
              </button>
            </div>
          )}
        </div>
      </div>
    );
  };

  if (isUpload) {
    return (
      <aside className={`sidebar-right w-[400px] bg-white dark:bg-[#0d1117] border-l border-gray-200 dark:border-[#30363d] flex flex-col z-20 shrink-0 h-full ${revealClass}`}>
        <div className="p-4 border-b border-gray-200 dark:border-[#30363d] flex items-center justify-between bg-white dark:bg-[#0d1117]">
          <h2 className="font-heading text-sm text-gray-900 dark:text-gray-100">Processing Queue</h2>
        </div>
        <div className="flex-1 flex flex-col items-center justify-center p-8 space-y-4">
          <div className="size-12 bg-gray-100 dark:bg-[#161b22] flex items-center justify-center rounded-lg">
            <span className="material-symbols-outlined text-gray-400 dark:text-gray-500 text-[24px]">pending_actions</span>
          </div>
          <div className="text-center space-y-1 max-w-[240px]">
            <h3 className="text-gray-900 dark:text-gray-100 font-heading text-sm">Waiting for Documents</h3>
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
    <aside className={`sidebar-right w-[400px] bg-white dark:bg-[#0d1117] border-l border-gray-200 dark:border-[#30363d] flex flex-col z-20 shrink-0 h-full ${revealClass}`}>
      <div className="p-4 border-b border-gray-200 dark:border-[#30363d] flex items-center justify-between bg-white dark:bg-[#0d1117] shrink-0">
        <h2 className="font-heading text-sm text-gray-900 dark:text-gray-100">Verification Chat</h2>
      </div>

      {/* Document selector */}
      <div className="p-3 border-b border-gray-200 dark:border-[#30363d] shrink-0">
        <label className="text-[10px] font-semibold uppercase tracking-wider text-gray-600 dark:text-gray-400 block mb-1.5">Document</label>
        <select
          className="w-full p-2.5 bg-white dark:bg-[#161b22] border border-gray-300 dark:border-[#30363d] text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-1 focus:ring-primary rounded transition-shadow focus:shadow-md"
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

      {/* Scrollable message list */}
      <div className="flex-1 overflow-y-auto p-3 space-y-4 min-h-0">
        {documents.length === 0 ? (
          <p className="text-sm text-gray-600 dark:text-gray-400 reveal visible">Upload a document first to run queries.</p>
        ) : messages.length === 0 && !queryLoading ? (
          <div className="flex flex-col items-center justify-center h-full text-center reveal visible">
            <div className="size-10 bg-gray-100 dark:bg-[#161b22] flex items-center justify-center rounded-lg mb-3">
              <span className="material-symbols-outlined text-gray-400 dark:text-gray-500 text-[20px]">chat</span>
            </div>
            <p className="text-sm text-gray-500 dark:text-gray-500">Ask a question below.</p>
            <p className="text-xs text-gray-400 dark:text-gray-600 mt-1">Verified answers will appear here.</p>
          </div>
        ) : (
          <>
            {messages.map((msg, i) => (
              <div
                key={i}
                className={msg.role === 'user' ? 'flex justify-end' : 'flex justify-start'}
              >
                {msg.role === 'user' ? (
                  <div className="reveal visible max-w-[85%] rounded-lg px-3 py-2 bg-primary/10 dark:bg-primary/20 text-gray-900 dark:text-gray-100 text-sm" style={{ transitionDelay: `${i * 0.03}s` }}>
                    {msg.text}
                  </div>
                ) : (
                  <div className="max-w-[95%] w-full">{renderAssistantBlock(msg, i)}</div>
                )}
              </div>
            ))}
            {queryLoading && <TypingIndicator />}
            <div ref={messagesEndRef} />
          </>
        )}
      </div>

      {/* Fixed input at bottom */}
      <div className="p-3 border-t border-gray-200 dark:border-[#30363d] bg-gray-50 dark:bg-[#161b22] shrink-0 space-y-2">
        <textarea
          className="w-full min-h-[80px] p-3 bg-white dark:bg-[#0d1117] border border-gray-300 dark:border-[#30363d] text-gray-900 dark:text-gray-100 text-sm resize-y focus:outline-none focus:ring-1 focus:ring-primary rounded font-mono transition-shadow focus:shadow-md"
          placeholder="e.g. What is pin 5? Maximum voltage?"
          value={question}
          maxLength={MAX_QUESTION_LENGTH}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              handleVerify();
            }
          }}
          disabled={queryLoading}
          aria-label="Verification question"
        />
        {question.length > MAX_QUESTION_LENGTH * 0.8 && (
          <p className="text-[10px] text-gray-400 dark:text-gray-500 text-right font-mono">
            {question.length}/{MAX_QUESTION_LENGTH}
          </p>
        )}
        <button
          type="button"
          onClick={handleVerify}
          disabled={!selectedDocId || !question.trim() || queryLoading}
          className="w-full flex items-center justify-center gap-2 bg-primary hover:bg-[#0052a3] disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium py-2.5 px-4 transition-all hover:shadow-md active:scale-[0.98] rounded"
        >
          <span className="material-symbols-outlined text-[18px]">send</span>
          {queryLoading ? 'Verifying…' : 'Send'}
        </button>
      </div>

      <div className="p-2 border-t border-gray-200 dark:border-[#30363d] bg-gray-50 dark:bg-[#161b22] text-center shrink-0">
        {usage ? (
          <p className="text-[10px] text-gray-500 dark:text-gray-500 font-mono">
            {usage.queries.used}/{usage.queries.limit} queries
            {usage.queries.remaining === 0 && (
              <span className="text-amber-600 dark:text-amber-400 font-medium ml-1">• Limit reached</span>
            )}
            {usage.queries.remaining > 0 && (
              <span className="text-gray-400 dark:text-gray-600"> • {usage.queries.remaining} remaining</span>
            )}
          </p>
        ) : (
          <p className="text-[10px] text-gray-500 dark:text-gray-500 font-mono">Akili • Coordinate-grounded verification</p>
        )}
      </div>
    </aside>
  );
};

export default SidebarRight;
