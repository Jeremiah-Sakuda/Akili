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
import { getDocuments } from './api';

const documentToFile = (d: DocumentSummary, activeId: string | null) => ({
  id: d.doc_id,
  name: d.filename || d.doc_id,
  meta: `${d.units_count} units · ${d.bijections_count} bijections · ${d.grids_count} grids`,
  icon: 'description',
  active: d.doc_id === activeId,
});

const App: React.FC = () => {
  const { user, loading: authLoading } = useAuth();
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null);
  const [viewState, setViewState] = useState<AppState>(AppState.UPLOAD);
  const [queryResult, setQueryResult] = useState<QueryResponse | null>(null);
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
    if (state !== AppState.UPLOAD) setQueryResult(null);
  };

  const handleIngestSuccess = (newDocId: string) => {
    setSelectedDocId(newDocId);
    refreshDocuments().then(() => setViewState(AppState.VERIFIED));
    setQueryResult(null);
  };

  const handleSelectDoc = (docId: string) => {
    setSelectedDocId(docId);
    setViewState(AppState.VERIFIED);
    setQueryResult(null);
    setOverlayProof(null);
  };

  const handleShowProof = useCallback((proof: ProofPoint[] | null) => {
    setOverlayProof(proof);
    setViewState(AppState.VERIFIED);
  }, []);

  const handleQueryResult = (result: QueryResponse) => {
    setQueryResult(result);
    setViewState(result.status === 'refuse' ? AppState.REFUSED : AppState.VERIFIED);
  };

  const displayState = queryResult?.status === 'refuse' ? AppState.REFUSED : viewState;
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
          queryResult={queryResult}
          onQueryResult={handleQueryResult}
          onSelectDoc={handleSelectDoc}
          onShowProof={handleShowProof}
          queryLoading={queryLoading}
          setQueryLoading={setQueryLoading}
        />
      </div>
    </div>
  );
};

export default App;
