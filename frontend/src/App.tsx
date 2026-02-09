import React, { useCallback, useEffect, useState } from 'react';
import Header from './components/Header';
import SidebarLeft from './components/SidebarLeft';
import SidebarRight from './components/SidebarRight';
import DocumentViewer from './components/DocumentViewer';
import FileUploader from './components/FileUploader';
import LoginPage from './components/LoginPage';
import { useAuth } from './contexts/AuthContext';
import { AppState } from './types';
import type { DocumentSummary, ProofPoint, QueryResponse } from './api';
import { deleteDocument as apiDeleteDocument, getDocuments, query as apiQuery, isRefuse } from './api';

const documentToFile = (d: DocumentSummary, activeId: string | null) => ({
  id: d.doc_id,
  name: d.filename || d.doc_id,
  meta: `${d.units_count ?? 0} units · ${d.bijections_count ?? 0} bijections · ${d.grids_count ?? 0} grids`,
  icon: 'description',
  active: d.doc_id === activeId,
});

const App: React.FC = () => {
  const { user, loading: authLoading } = useAuth();
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null);
  const [viewState, setViewState] = useState<AppState>(AppState.UPLOAD);
  const [messages, setMessages] = useState<import('./api').ChatMessage[]>([]);
  const [overlayProof, setOverlayProof] = useState<ProofPoint[] | null>(null);
  const [loadingDocs, setLoadingDocs] = useState(true);
  const [queryLoading, setQueryLoading] = useState(false);

  const refreshDocuments = useCallback(async () => {
    setLoadingDocs(true);
    try {
      const list = await getDocuments();
      setDocuments(list);
      if (list.length === 0) setSelectedDocId(null);
      else setSelectedDocId((prev) => (prev && list.some((d) => d.doc_id === prev) ? prev : list[0].doc_id));
    } catch {
      setDocuments([]);
    } finally {
      setLoadingDocs(false);
    }
  }, []);

  useEffect(() => {
    refreshDocuments();
  }, [refreshDocuments]);

  const handleStateChange = (state: AppState) => {
    setViewState(state);
    if (state !== AppState.UPLOAD) setMessages([]);
  };

  const handleIngestSuccess = (newDocId: string) => {
    setSelectedDocId(newDocId);
    refreshDocuments().then(() => setViewState(AppState.VERIFIED));
    setMessages([]);
  };

  const handleSelectDoc = (docId: string) => {
    setSelectedDocId(docId);
    setViewState(AppState.VERIFIED);
    setMessages([]);
    setOverlayProof(null);
  };

  const handleDeleteDocument = useCallback(
    async (docId: string) => {
      try {
        await apiDeleteDocument(docId);
        await refreshDocuments();
        if (selectedDocId === docId) {
          setSelectedDocId(null);
          setOverlayProof(null);
          setMessages([]);
        }
      } catch {
        // Error could be shown via toast; for now rely on refreshDocuments not updating
      }
    },
    [refreshDocuments, selectedDocId]
  );

  const handleShowProof = useCallback((proof: ProofPoint[] | null) => {
    setOverlayProof(proof);
    setViewState(AppState.VERIFIED);
  }, []);

  const handleSendQuestion = useCallback(
    async (question: string) => {
      if (!selectedDocId?.trim() || !question.trim()) return;
      setMessages((m) => [...m, { role: 'user', text: question.trim() }]);
      setQueryLoading(true);
      try {
        const result = await apiQuery(selectedDocId, question.trim(), { includeFormattedAnswer: true });
        const text = isRefuse(result) ? result.reason : (result.formatted_answer ?? result.answer);
        setMessages((m) => [...m, { role: 'assistant', text, response: result }]);
        setViewState(isRefuse(result) ? AppState.REFUSED : AppState.VERIFIED);
      } catch {
        setMessages((m) => [
          ...m,
          { role: 'assistant', text: 'Query failed. Is the API running?', response: { status: 'refuse', reason: 'Query failed.' } },
        ]);
      } finally {
        setQueryLoading(false);
      }
    },
    [selectedDocId]
  );

  const displayState =
    messages.length > 0 && messages[messages.length - 1].role === 'assistant' && messages[messages.length - 1].response
      ? (messages[messages.length - 1].response!.status === 'refuse' ? AppState.REFUSED : AppState.VERIFIED)
      : viewState;
  const files = documents.map((d) => documentToFile(d, selectedDocId));

  if (authLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-white dark:bg-[#0d1117]">
        <div className="text-gray-600 dark:text-gray-400 text-sm font-medium">Loading…</div>
      </div>
    );
  }

  if (!user) {
    return <LoginPage />;
  }

  return (
    <div className="flex flex-col h-screen bg-white dark:bg-[#0d1117]">
      <Header />

      <div className="flex flex-1 overflow-hidden">
        <SidebarLeft
          currentState={displayState}
          onStateChange={handleStateChange}
          files={files}
          selectedDocId={selectedDocId}
          loading={loadingDocs}
          onSelectFile={handleSelectDoc}
          onDeleteDocument={handleDeleteDocument}
        />

        <main className="flex-1 bg-gray-50 dark:bg-[#0d1117] relative flex flex-col overflow-hidden">
          {viewState === AppState.UPLOAD ? (
            <FileUploader onSuccess={handleIngestSuccess} onBack={() => handleStateChange(AppState.VERIFIED)} />
          ) : (
            <>
              <div className="h-10 bg-white dark:bg-[#161b22] border-b border-gray-200 dark:border-[#30363d] flex items-center justify-between px-4 z-10">
                <div className="flex items-center gap-2">
                  <button className="p-1 hover:bg-gray-100 dark:hover:bg-[#0d1117] text-gray-600 dark:text-gray-400" type="button">
                    <span className="material-symbols-outlined text-[18px]">menu</span>
                  </button>
                  <span className="text-sm font-medium text-gray-900 dark:text-gray-100">
                    {selectedDocId
                      ? documents.find((d) => d.doc_id === selectedDocId)?.filename ?? selectedDocId
                      : 'Select a document'}
                  </span>
                </div>
                <div className="flex items-center gap-1 bg-gray-100 dark:bg-[#0d1117] border border-gray-200 dark:border-[#30363d] p-0.5">
                  <button className="p-1 hover:bg-white dark:hover:bg-[#161b22] transition-colors text-gray-700 dark:text-gray-300" type="button">
                    <span className="material-symbols-outlined text-[16px]">remove</span>
                  </button>
                  <span className="text-xs font-medium px-2 text-gray-700 dark:text-gray-300 font-mono">100%</span>
                  <button className="p-1 hover:bg-white dark:hover:bg-[#161b22] transition-colors text-gray-700 dark:text-gray-300" type="button">
                    <span className="material-symbols-outlined text-[16px]">add</span>
                  </button>
                </div>
                <div className="flex items-center gap-1">
                  <button className="p-1.5 hover:bg-gray-100 dark:hover:bg-[#0d1117] text-gray-600 dark:text-gray-400" type="button">
                    <span className="material-symbols-outlined text-[18px]">download</span>
                  </button>
                  <button className="p-1.5 hover:bg-gray-100 dark:hover:bg-[#0d1117] text-gray-600 dark:text-gray-400" type="button">
                    <span className="material-symbols-outlined text-[18px]">print</span>
                  </button>
                </div>
              </div>

              <DocumentViewer
                docId={selectedDocId}
                overlayProof={overlayProof}
              />
            </>
          )}
        </main>

        <SidebarRight
          currentState={displayState}
          onStateChange={handleStateChange}
          selectedDocId={selectedDocId}
          documents={documents}
          messages={messages}
          onSendQuestion={handleSendQuestion}
          onSelectDoc={handleSelectDoc}
          onShowProof={handleShowProof}
          queryLoading={queryLoading}
        />
      </div>
    </div>
  );
};

export default App;
