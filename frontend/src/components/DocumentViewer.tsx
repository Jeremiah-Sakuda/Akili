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

  // Scroll to first proof page when overlayProof is set (delay so refs are populated)
  useEffect(() => {
    if (!overlayProof?.length) return;
    const first = overlayProof[0];
    const page = first?.page ?? 0;
    const t = setTimeout(() => {
      const el = pageRefsRef.current.get(page);
      if (el && containerRef.current) {
        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }, 150);
    return () => clearTimeout(t);
  }, [overlayProof]);

  const setPageRef = useCallback((pageIndex: number, el: HTMLDivElement | null) => {
    if (el) pageRefsRef.current.set(pageIndex, el);
  }, []);

  if (!docId) {
    return (
      <div className="flex-1 overflow-y-auto p-8 flex items-center justify-center bg-gray-100 dark:bg-[#0d1117]">
        <div className="text-gray-500 dark:text-gray-400 text-sm">Select a document to view</div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex-1 overflow-y-auto p-8 flex items-center justify-center bg-gray-100 dark:bg-[#0d1117]">
        <div className="text-gray-600 dark:text-gray-400 text-sm">Loading PDF…</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex-1 overflow-y-auto p-8 flex items-center justify-center bg-gray-100 dark:bg-[#0d1117]">
        <div className="text-amber-700 dark:text-amber-400 text-sm max-w-md text-center">{error}</div>
      </div>
    );
  }

  if (!pdfDoc) {
    return (
      <div className="flex-1 overflow-y-auto p-8 flex items-center justify-center bg-gray-100 dark:bg-[#0d1117]">
        <div className="text-gray-500 dark:text-gray-400 text-sm">No document loaded</div>
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className="flex-1 overflow-y-auto p-6 flex flex-col items-center gap-6 bg-gray-200 dark:bg-[#161b22]"
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
      className="relative bg-white border border-gray-300 dark:border-[#30363d]"
      style={pageSize ? { width: pageSize.width, height: pageSize.height } : undefined}
    >
      <canvas ref={canvasRef} className="block" />
      {pageSize && proofPoints.length > 0 && (
        <div
          className="absolute inset-0 pointer-events-none"
          style={{ width: pageSize.width, height: pageSize.height }}
        >
          {proofPoints.map((p, i) => {
            // Full-width horizontal band: 18% of page height, centered on proof y (normalized 0–1, top-left origin).
            const bandHeight = 0.18;
            const half = bandHeight / 2;
            const centerY = p.bbox
              ? (p.bbox.y1 + p.bbox.y2) / 2
              : p.y;
            const top = Math.max(0, Math.min(1 - bandHeight, centerY - half));
            return (
              <div
                key={i}
                className="absolute border-2 border-emerald-500 dark:border-emerald-400 bg-emerald-500/20 dark:bg-emerald-400/20"
                style={{
                  left: 0,
                  top: `${top * 100}%`,
                  width: '100%',
                  height: `${bandHeight * 100}%`,
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
