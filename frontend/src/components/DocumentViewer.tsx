import React, { useCallback, useEffect, useRef, useState } from 'react';
import * as pdfjsLib from 'pdfjs-dist';
import type { ProofPoint } from '../api';
import { getDocumentFile } from '../api';

// PDF.js worker for Vite
import pdfjsWorker from 'pdfjs-dist/build/pdf.worker.mjs?url';
if (pdfjsWorker) {
  pdfjsLib.GlobalWorkerOptions.workerSrc = pdfjsWorker;
}

interface DocumentViewerProps {
  docId?: string | null;
  overlayProof?: ProofPoint[] | null;
}

const SCALE = 1.5;

const DocumentViewer: React.FC<DocumentViewerProps> = ({ docId, overlayProof }) => {
  const [pdfDoc, setPdfDoc] = useState<pdfjsLib.PDFDocumentProxy | null>(null);
  const [numPages, setNumPages] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const blobUrlRef = useRef<string | null>(null);
  const pageRefsRef = useRef<Map<number, HTMLDivElement | null>>(new Map());
  const containerRef = useRef<HTMLDivElement | null>(null);

  // Load PDF when docId changes
  useEffect(() => {
    if (!docId) {
      if (blobUrlRef.current) {
        URL.revokeObjectURL(blobUrlRef.current);
        blobUrlRef.current = null;
      }
      setPdfDoc(null);
      setNumPages(0);
      setError(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    getDocumentFile(docId)
      .then((url) => {
        if (cancelled) {
          URL.revokeObjectURL(url);
          return;
        }
        if (blobUrlRef.current) URL.revokeObjectURL(blobUrlRef.current);
        blobUrlRef.current = url;
        return pdfjsLib.getDocument({ url }).promise;
      })
      .then((doc) => {
        if (cancelled || !doc) return;
        setPdfDoc(doc);
        setNumPages(doc.numPages);
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Failed to load PDF');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [docId]);

  // Revoke blob URL on unmount
  useEffect(() => {
    return () => {
      if (blobUrlRef.current) {
        URL.revokeObjectURL(blobUrlRef.current);
        blobUrlRef.current = null;
      }
    };
  }, []);

  // Scroll to first proof page when overlayProof is set
  useEffect(() => {
    if (!overlayProof?.length) return;
    const first = overlayProof[0];
    const page = first?.page ?? 0;
    const el = pageRefsRef.current.get(page);
    if (el && containerRef.current) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }, [overlayProof]);

  const setPageRef = useCallback((pageIndex: number, el: HTMLDivElement | null) => {
    if (el) pageRefsRef.current.set(pageIndex, el);
  }, []);

  if (!docId) {
    return (
      <div className="flex-1 overflow-y-auto p-8 flex items-center justify-center bg-[#525659]">
        <div className="text-slate-400 text-sm">Select a document to view</div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex-1 overflow-y-auto p-8 flex items-center justify-center bg-[#525659]">
        <div className="text-slate-300 text-sm">Loading PDF…</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex-1 overflow-y-auto p-8 flex items-center justify-center bg-[#525659]">
        <div className="text-amber-200 text-sm max-w-md text-center">{error}</div>
      </div>
    );
  }

  if (!pdfDoc) {
    return (
      <div className="flex-1 overflow-y-auto p-8 flex items-center justify-center bg-[#525659]">
        <div className="text-slate-400 text-sm">No document loaded</div>
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className="flex-1 overflow-y-auto p-6 flex flex-col items-center gap-6 bg-[#525659]"
    >
      {Array.from({ length: numPages }, (_, i) => i).map((pageIndex) => (
        <PageWithOverlay
          key={pageIndex}
          pdfDoc={pdfDoc}
          pageIndex={pageIndex}
          scale={SCALE}
          proofPoints={overlayProof?.filter((p) => (p.page ?? 0) === pageIndex) ?? []}
          setPageRef={setPageRef}
        />
      ))}
    </div>
  );
};

interface PageWithOverlayProps {
  pdfDoc: pdfjsLib.PDFDocumentProxy;
  pageIndex: number;
  scale: number;
  proofPoints: ProofPoint[];
  setPageRef: (pageIndex: number, el: HTMLDivElement | null) => void;
}

const PageWithOverlay: React.FC<PageWithOverlayProps> = ({
  pdfDoc,
  pageIndex,
  scale,
  proofPoints,
  setPageRef,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [pageSize, setPageSize] = useState<{ width: number; height: number } | null>(null);

  useEffect(() => {
    let cancelled = false;
    pdfDoc.getPage(pageIndex + 1).then((page) => {
      if (cancelled) return;
      const viewport = page.getViewport({ scale });
      const w = viewport.width;
      const h = viewport.height;
      setPageSize({ width: w, height: h });
      const canvas = canvasRef.current;
      if (!canvas) return;
      const ctx = canvas.getContext('2d');
      if (!ctx) return;
      canvas.width = w;
      canvas.height = h;
      page.render({
        canvasContext: ctx,
        viewport,
        canvas,
      }).promise.catch(() => {});
    });
    return () => {
      cancelled = true;
    };
  }, [pdfDoc, pageIndex, scale]);

  return (
    <div
      ref={(el) => setPageRef(pageIndex, el)}
      className="relative bg-white shadow-lg"
      style={pageSize ? { width: pageSize.width, height: pageSize.height } : undefined}
    >
      <canvas ref={canvasRef} className="block" />
      {pageSize && proofPoints.length > 0 && (
        <div
          className="absolute inset-0 pointer-events-none"
          style={{ width: pageSize.width, height: pageSize.height }}
        >
          {proofPoints.map((p, i) => {
            // Normalized 0–1: prompt says top-left origin, y down. If overlay still looks
            // vertically off, the model may use y-up; flip point for display.
            const flipY = (y: number) => 1 - y;
            if (p.bbox) {
              const { x1, y1, x2, y2 } = p.bbox;
              return (
                <div
                  key={i}
                  className="absolute border-2 border-emerald-500 bg-emerald-500/30 rounded"
                  style={{
                    left: `${x1 * 100}%`,
                    top: `${y1 * 100}%`,
                    width: `${(x2 - x1) * 100}%`,
                    height: `${(y2 - y1) * 100}%`,
                    minWidth: 8,
                    minHeight: 8,
                  }}
                  title={`Proof (${p.x.toFixed(2)}, ${p.y.toFixed(2)})`}
                />
              );
            }
            const top = flipY(p.y);
            return (
              <div
                key={i}
                className="absolute border-2 border-emerald-500 bg-emerald-500/30 rounded"
                style={{
                  left: `${(p.x - 0.02) * 100}%`,
                  top: `${(top - 0.02) * 100}%`,
                  width: '4%',
                  height: '4%',
                  minWidth: 12,
                  minHeight: 12,
                }}
                title={`Proof (${p.x.toFixed(2)}, ${p.y.toFixed(2)})`}
              />
            );
          })}
        </div>
      )}
    </div>
  );
};

export default DocumentViewer;
