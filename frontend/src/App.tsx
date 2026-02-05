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

  const handleQueryResult = (result: QueryResponse) => {
    setQueryResult(result);
    setViewState(result.status === 'refuse' ? AppState.REFUSED : AppState.VERIFIED);
  };

  const displayState = queryResult?.status === 'refuse' ? AppState.REFUSED : viewState;
  const files = documents.map((d) => documentToFile(d, selectedDocId));

  if (authLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background-light">
        <div className="text-slate-500 text-sm font-medium">Loading…</div>
      </div>
    );
  }

  if (!user) {
    return <LoginPage />;
  }

  return (
    <div className="flex flex-col h-screen">
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

        <main className="flex-1 bg-slate-100/80 relative flex flex-col overflow-hidden">
          {viewState === AppState.UPLOAD ? (
            <FileUploader onSuccess={handleIngestSuccess} onBack={() => handleStateChange(AppState.VERIFIED)} />
          ) : (
            <>
              <div className="h-12 bg-white border-b border-gray-200 flex items-center justify-between px-4 shadow-sm z-10">
                <div className="flex items-center gap-2">
                  <button className="p-1.5 hover:bg-gray-100 rounded text-slate-500" type="button">
                    <span className="material-symbols-outlined text-[20px]">menu</span>
                  </button>
                  <span className="text-sm font-medium text-slate-700">
                    {selectedDocId
                      ? documents.find((d) => d.doc_id === selectedDocId)?.filename ?? selectedDocId
                      : 'Select a document'}
                  </span>
                </div>
                <div className="flex items-center gap-1 bg-gray-100 rounded-lg p-1">
                  <button className="p-1 hover:bg-white rounded shadow-sm transition-all text-slate-600" type="button">
                    <span className="material-symbols-outlined text-[18px]">remove</span>
                  </button>
                  <span className="text-xs font-semibold px-2 text-slate-600">100%</span>
                  <button className="p-1 hover:bg-white rounded shadow-sm transition-all text-slate-600" type="button">
                    <span className="material-symbols-outlined text-[18px]">add</span>
                  </button>
                </div>
                <div className="flex items-center gap-2">
                  <button className="p-1.5 hover:bg-gray-100 rounded text-slate-500" type="button">
                    <span className="material-symbols-outlined text-[20px]">download</span>
                  </button>
                  <button className="p-1.5 hover:bg-gray-100 rounded text-slate-500" type="button">
                    <span className="material-symbols-outlined text-[20px]">print</span>
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
          onShowProof={setOverlayProof}
          queryLoading={queryLoading}
          setQueryLoading={setQueryLoading}
        />
      </div>
    </div>
  );
};

export default App;
