import React, { useCallback, useRef, useState } from 'react';
import { ingestStream, type IngestResponse, type IngestProgressEvent } from '../api';

type UploadPhase =
  | 'idle'
  | 'uploading'
  | 'rendering'
  | 'extracting'
  | 'canonicalizing'
  | 'storing'
  | 'done'
  | 'error';

const PHASES: { key: UploadPhase; label: string; description: string }[] = [
  { key: 'uploading', label: 'Uploading file', description: 'Sending PDF to server' },
  { key: 'rendering', label: 'Rendering PDF pages', description: 'Converting pages to images (PyMuPDF)' },
  { key: 'extracting', label: 'Extracting with Gemini', description: 'Per-page vision extraction' },
  { key: 'canonicalizing', label: 'Canonicalizing', description: 'Normalizing facts per page' },
  { key: 'storing', label: 'Storing', description: 'Writing to database' },
  { key: 'done', label: 'Done', description: 'Document ready for verification' },
];

const PHASE_ORDER: UploadPhase[] = ['uploading', 'rendering', 'extracting', 'canonicalizing', 'storing', 'done'];

interface FileUploaderProps {
  onSuccess: (docId: string, result?: IngestResponse) => void;
  onBack?: () => void;
}

/** Per-file tracking for batch uploads */
interface FileProgress {
  file: File;
  phase: UploadPhase;
  progress: number;
  progressDetail: string | null;
  result: IngestResponse | null;
  error: string | null;
}

/** Progress bar reaches this over PROGRESS_DURATION_MS while loading (then jumps to 100 when done). */
const PROGRESS_DURATION_MS = 90_000; // 90 seconds to reach 90%
const PROGRESS_CAP = 90;

const FileUploader: React.FC<FileUploaderProps> = ({ onSuccess, onBack }) => {
  const inputRef = useRef<HTMLInputElement>(null);
  const [loading, setLoading] = useState(false);
  // Single-file state (used when only 1 file)
  const [phase, setPhase] = useState<UploadPhase>('idle');
  const [progress, setProgress] = useState(0);
  const [progressDetail, setProgressDetail] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<IngestResponse | null>(null);
  const [copied, setCopied] = useState(false);
  const progressIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const progressStartRef = useRef<number>(0);

  // Batch state
  const [batchFiles, setBatchFiles] = useState<FileProgress[]>([]);
  const [batchIndex, setBatchIndex] = useState(-1);
  const isBatch = batchFiles.length > 1;

  const clearProgressInterval = useCallback(() => {
    if (progressIntervalRef.current !== null) {
      clearInterval(progressIntervalRef.current);
      progressIntervalRef.current = null;
    }
  }, []);

  const copyDocId = async () => {
    if (!result?.doc_id) return;
    try {
      await navigator.clipboard.writeText(result.doc_id);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  };

  const processProgressEvent = (event: IngestProgressEvent) => {
    if (event.phase === 'rendering' || event.phase === 'rendering_done') {
      setPhase('rendering');
      setProgressDetail(event.total_pages != null ? `${event.total_pages} page(s)` : null);
    } else if (event.phase === 'extracting') {
      setPhase('extracting');
      const total = event.total_pages ?? 0;
      const page = event.page ?? 0;
      setProgressDetail(total > 0 ? `Page ${page + 1} of ${total}` : null);
    } else if (event.phase === 'canonicalizing') {
      setPhase('canonicalizing');
      const total = event.total_pages ?? 0;
      const page = event.page ?? 0;
      setProgressDetail(total > 0 ? `Page ${page + 1} of ${total}` : null);
    } else if (event.phase === 'storing') {
      setPhase('storing');
      setProgressDetail(null);
    } else if (event.phase === 'done') {
      clearProgressInterval();
      setProgress(100);
      setPhase('done');
      setProgressDetail(null);
    }
  };

  const ingestSingleFile = async (file: File): Promise<IngestResponse> => {
    setPhase('uploading');
    setProgress(0);
    setProgressDetail(null);
    progressStartRef.current = Date.now();

    progressIntervalRef.current = setInterval(() => {
      const elapsed = Date.now() - progressStartRef.current;
      const p = Math.min(PROGRESS_CAP, (elapsed / PROGRESS_DURATION_MS) * PROGRESS_CAP);
      setProgress(Math.round(p));
    }, 500);

    const data = await ingestStream(file, processProgressEvent);
    clearProgressInterval();
    return data;
  };

  const handleFile = async (files: FileList | null) => {
    if (!files?.length) return;

    // Validate all files are PDFs
    const pdfFiles: File[] = [];
    for (let i = 0; i < files.length; i++) {
      if (!files[i].name.toLowerCase().endsWith('.pdf')) {
        setError(`"${files[i].name}" is not a PDF. Only PDF files are accepted.`);
        return;
      }
      pdfFiles.push(files[i]);
    }

    setError(null);
    setResult(null);
    setLoading(true);

    if (pdfFiles.length === 1) {
      // Single file — use original behavior
      setBatchFiles([]);
      setBatchIndex(-1);
      try {
        const data = await ingestSingleFile(pdfFiles[0]);
        setResult(data);
        onSuccess(data.doc_id, data);
      } catch (e) {
        clearProgressInterval();
        setProgress(0);
        setPhase('error');
        setProgressDetail(null);
        setError(e instanceof Error ? e.message : 'Upload failed.');
      } finally {
        setLoading(false);
      }
    } else {
      // Batch — process sequentially
      const initialBatch: FileProgress[] = pdfFiles.map((f) => ({
        file: f,
        phase: 'idle' as UploadPhase,
        progress: 0,
        progressDetail: null,
        result: null,
        error: null,
      }));
      setBatchFiles(initialBatch);

      for (let i = 0; i < pdfFiles.length; i++) {
        setBatchIndex(i);
        setBatchFiles((prev) =>
          prev.map((fp, j) => (j === i ? { ...fp, phase: 'uploading', progress: 0 } : fp))
        );

        try {
          const data = await ingestSingleFile(pdfFiles[i]);
          setBatchFiles((prev) =>
            prev.map((fp, j) =>
              j === i ? { ...fp, phase: 'done', progress: 100, result: data, error: null } : fp
            )
          );
          onSuccess(data.doc_id, data);
        } catch (e) {
          clearProgressInterval();
          const errorMsg = e instanceof Error ? e.message : 'Upload failed.';
          setBatchFiles((prev) =>
            prev.map((fp, j) =>
              j === i ? { ...fp, phase: 'error', progress: 0, error: errorMsg } : fp
            )
          );
        }
      }

      setPhase('done');
      setProgress(100);
      setLoading(false);
      setBatchIndex(-1);
    }
  };

  React.useEffect(() => {
    return () => clearProgressInterval();
  }, [clearProgressInterval]);

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    handleFile(e.dataTransfer.files);
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    handleFile(e.target.files);
    e.target.value = '';
  };

  const completedCount = batchFiles.filter((f) => f.phase === 'done').length;
  const failedCount = batchFiles.filter((f) => f.phase === 'error').length;

  return (
    <div
      className="file-uploader-root flex-1 bg-transparent relative flex flex-col items-center justify-center p-8 overflow-hidden h-full"
      onDrop={handleDrop}
      onDragOver={(e) => e.preventDefault()}
    >
      <div className="w-full max-w-[640px] z-10">
        {onBack && (
          <button
            type="button"
            onClick={onBack}
            className="mb-4 text-sm text-gray-600 dark:text-gray-400 hover:text-primary flex items-center gap-1 transition-colors"
          >
            <span className="material-symbols-outlined text-[16px]">arrow_back</span>
            Back
          </button>
        )}
        <div className="mb-8 text-center reveal visible">
          <h2 className="text-xl font-heading text-gray-900 dark:text-gray-100 tracking-tight">Upload Technical Document</h2>
          <p className="text-gray-600 dark:text-gray-400 mt-2 text-sm">Ingest PDFs for verification analysis</p>
        </div>

        <div
          className="group relative bg-white dark:bg-[#161b22] w-full border-2 border-dashed border-gray-300 dark:border-[#30363d] hover:border-primary dark:hover:border-primary transition-colors cursor-pointer overflow-hidden rounded-xl"
          onClick={() => !loading && inputRef.current?.click()}
          onKeyDown={(e) => e.key === 'Enter' && inputRef.current?.click()}
          role="button"
          tabIndex={0}
        >
          <label htmlFor="akili-pdf-file-input" className="sr-only">
            Choose PDF file
          </label>
          <input
            ref={inputRef}
            id="akili-pdf-file-input"
            name="file"
            className="absolute inset-0 opacity-0 cursor-pointer w-full h-full pointer-events-none"
            type="file"
            accept=".pdf,application/pdf"
            multiple
            onChange={handleChange}
            disabled={loading}
          />
          <div className="relative z-10 flex flex-col items-center justify-center min-h-64 p-6">
            {loading || phase === 'done' ? (
              <>
                <div className="size-12 bg-primary/10 dark:bg-primary/20 flex items-center justify-center mb-4">
                  <span className="material-symbols-outlined text-[24px] text-primary">
                    {phase === 'done' ? 'check_circle' : 'hourglass_empty'}
                  </span>
                </div>

                {isBatch ? (
                  <>
                    <p className="text-base font-medium text-gray-900 dark:text-gray-100">
                      {loading
                        ? `Processing file ${batchIndex + 1} of ${batchFiles.length}`
                        : `Batch complete: ${completedCount}/${batchFiles.length} succeeded`}
                    </p>
                    {loading && (
                      <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                        {batchFiles[batchIndex]?.file.name}
                      </p>
                    )}
                  </>
                ) : (
                  <>
                    <p className="text-base font-medium text-gray-900 dark:text-gray-100">
                      {phase === 'done' ? 'Document ready' : `Phase: ${PHASES.find((p) => p.key === phase)?.label ?? phase}`}
                    </p>
                    <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                      {phase === 'done'
                        ? 'Canonical facts stored'
                        : progressDetail
                          ? `${PHASES.find((p) => p.key === phase)?.description ?? '…'} — ${progressDetail}`
                          : PHASES.find((p) => p.key === phase)?.description ?? '…'}
                    </p>
                  </>
                )}

                {loading && (
                  <div className="mt-4 w-full max-w-xs">
                    <div className="h-2 bg-gray-200 dark:bg-[#21262d] rounded-full overflow-hidden">
                      <div
                        className="h-full bg-primary transition-all duration-300 ease-out"
                        style={{ width: `${progress}%` }}
                        role="progressbar"
                        aria-valuenow={progress}
                        aria-valuemin={0}
                        aria-valuemax={100}
                        aria-label="Extraction progress"
                      />
                    </div>
                    {isBatch && (
                      <p className="text-xs text-gray-500 dark:text-gray-400 mt-1.5 text-center">
                        Overall: {completedCount + failedCount}/{batchFiles.length} files
                      </p>
                    )}
                    {!isBatch && (
                      <p className="text-xs text-gray-500 dark:text-gray-400 mt-1.5">
                        Typically ~10–15 sec per page. Long documents may take several minutes.
                      </p>
                    )}
                  </div>
                )}

                {!isBatch && (loading || phase === 'done') && (
                  <ul className="mt-6 w-full max-w-xs space-y-2 text-left" aria-label="Upload pipeline status">
                    {PHASES.map((p) => {
                      const phaseIndex = PHASE_ORDER.indexOf(phase);
                      const stepIndex = PHASE_ORDER.indexOf(p.key);
                      const isComplete = phase === 'done' ? stepIndex <= PHASE_ORDER.length - 1 : stepIndex < phaseIndex;
                      const isActive = (!loading && phase === 'done' && stepIndex === PHASE_ORDER.length - 1) || (loading && stepIndex === phaseIndex);
                      return (
                        <li
                          key={p.key}
                          className={`flex items-center gap-3 text-sm ${isComplete ? 'text-emerald-600 dark:text-emerald-400' : isActive ? 'text-primary font-medium' : 'text-gray-500 dark:text-gray-500'}`}
                        >
                          <span className="flex size-5 shrink-0 items-center justify-center rounded-full bg-current/10">
                            {isComplete ? (
                              <span className="material-symbols-outlined text-[14px]">check</span>
                            ) : (
                              <span className="text-[10px] font-mono">{stepIndex + 1}</span>
                            )}
                          </span>
                          <span>{p.label}</span>
                          {isActive && loading && (
                            <span className="ml-auto text-xs text-gray-500 dark:text-gray-400">…</span>
                          )}
                        </li>
                      );
                    })}
                  </ul>
                )}

                {/* Batch file list */}
                {isBatch && (
                  <ul className="mt-6 w-full max-w-xs space-y-2 text-left" aria-label="Batch upload status">
                    {batchFiles.map((fp, i) => (
                      <li
                        key={i}
                        className={`flex items-center gap-3 text-sm ${
                          fp.phase === 'done'
                            ? 'text-emerald-600 dark:text-emerald-400'
                            : fp.phase === 'error'
                              ? 'text-red-600 dark:text-red-400'
                              : i === batchIndex
                                ? 'text-primary font-medium'
                                : 'text-gray-500 dark:text-gray-500'
                        }`}
                      >
                        <span className="flex size-5 shrink-0 items-center justify-center rounded-full bg-current/10">
                          {fp.phase === 'done' ? (
                            <span className="material-symbols-outlined text-[14px]">check</span>
                          ) : fp.phase === 'error' ? (
                            <span className="material-symbols-outlined text-[14px]">close</span>
                          ) : (
                            <span className="text-[10px] font-mono">{i + 1}</span>
                          )}
                        </span>
                        <span className="truncate">{fp.file.name}</span>
                        {i === batchIndex && loading && (
                          <span className="ml-auto text-xs text-gray-500 dark:text-gray-400">…</span>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
              </>
            ) : (
              <>
                <div className="size-12 bg-gray-100 dark:bg-[#0d1117] group-hover:bg-primary/10 dark:group-hover:bg-primary/20 flex items-center justify-center mb-4 transition-colors">
                  <span className="material-symbols-outlined text-[24px] text-gray-500 dark:text-gray-400 group-hover:text-primary transition-colors">
                    cloud_upload
                  </span>
                </div>
                <p className="text-base font-medium text-gray-900 dark:text-gray-100 mb-1">Drag & drop PDFs here</p>
                <p className="text-sm text-gray-600 dark:text-gray-400 mb-6">
                  or <span className="text-primary font-medium">browse your computer</span>
                </p>
                <div className="flex gap-2 text-xs text-gray-600 dark:text-gray-400 font-mono bg-gray-50 dark:bg-[#0d1117] px-3 py-1.5 border border-gray-200 dark:border-[#30363d]">
                  <span>SUPPORTED: PDF (single or multiple)</span>
                </div>
              </>
            )}
          </div>
        </div>

        {error && (
          <div className="mt-4 p-4 border border-amber-300 dark:border-amber-700 bg-amber-50 dark:bg-amber-900/20 text-amber-800 dark:text-amber-200 text-sm">
            {error}
          </div>
        )}

        {/* Single-file result */}
        {result && !loading && !isBatch && (
          <div className="mt-6 p-4 border border-emerald-300 dark:border-emerald-700 bg-emerald-50 dark:bg-emerald-900/20">
            <p className="text-sm font-semibold text-emerald-800 dark:text-emerald-300 mb-2">Document canonicalized</p>
            <div className="flex items-center gap-2 mb-1">
              <p className="text-xs font-mono text-gray-700 dark:text-gray-300">
                <span className="text-gray-500 dark:text-gray-500">doc_id:</span> {result.doc_id}
              </p>
              <button
                type="button"
                onClick={copyDocId}
                className="p-1 hover:bg-emerald-100 dark:hover:bg-emerald-900/40 text-gray-600 dark:text-gray-400 hover:text-emerald-700 dark:hover:text-emerald-300 transition-colors"
                title="Copy doc_id"
              >
                <span className="material-symbols-outlined text-[14px]">
                  {copied ? 'check' : 'content_copy'}
                </span>
              </button>
            </div>
            <p className="text-xs text-gray-700 dark:text-gray-300 font-mono">
              {result.units_count ?? 0} units · {result.bijections_count ?? 0} bijections · {result.grids_count ?? 0} grids
            </p>
            {result.extraction_warning && (
              <p className="text-xs text-amber-700 dark:text-amber-300 mt-2" role="alert">
                {result.extraction_warning}
              </p>
            )}
            {result.extraction_note && (
              <p className="text-xs text-amber-700 dark:text-amber-300 mt-2" role="status">
                {result.extraction_note}
              </p>
            )}
          </div>
        )}

        {/* Batch results summary */}
        {!loading && isBatch && (completedCount > 0 || failedCount > 0) && (
          <div className="mt-6 p-4 border border-emerald-300 dark:border-emerald-700 bg-emerald-50 dark:bg-emerald-900/20">
            <p className="text-sm font-semibold text-emerald-800 dark:text-emerald-300 mb-2">
              Batch upload complete
            </p>
            <p className="text-xs text-gray-700 dark:text-gray-300 font-mono">
              {completedCount} succeeded · {failedCount} failed · {batchFiles.length} total
            </p>
            {batchFiles.filter((f) => f.result).map((f, i) => (
              <div key={i} className="mt-2 text-xs font-mono text-gray-600 dark:text-gray-400">
                <span className="text-emerald-600 dark:text-emerald-400">✓</span> {f.file.name}: {f.result!.units_count} units, {f.result!.bijections_count} bijections, {f.result!.grids_count} grids
              </div>
            ))}
            {batchFiles.filter((f) => f.error).map((f, i) => (
              <div key={i} className="mt-2 text-xs font-mono text-red-600 dark:text-red-400">
                ✗ {f.file.name}: {f.error}
              </div>
            ))}
          </div>
        )}

        <div className="mt-8 grid grid-cols-2 gap-4 stagger">
          <div className="reveal visible bg-white dark:bg-[#161b22] p-4 border border-gray-200 dark:border-[#30363d] flex items-start gap-3 rounded-lg transition-all hover:shadow-sm">
            <div className="p-1.5 bg-emerald-50 dark:bg-emerald-900/30 text-emerald-600 dark:text-emerald-400 rounded">
              <span className="material-symbols-outlined text-[18px]">check_circle</span>
            </div>
            <div>
              <p className="text-[10px] font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-0.5">System Status</p>
              <p className="text-sm font-heading text-gray-900 dark:text-gray-100">Ready for Ingest</p>
            </div>
          </div>
          <div className="reveal visible bg-white dark:bg-[#161b22] p-4 border border-gray-200 dark:border-[#30363d] flex items-start gap-3 rounded-lg transition-all hover:shadow-sm" style={{ transitionDelay: '0.08s' }}>
            <div className="p-1.5 bg-primary/10 dark:bg-primary/20 text-primary rounded">
              <span className="material-symbols-outlined text-[18px]">api</span>
            </div>
            <div>
              <p className="text-[10px] font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-0.5">API</p>
              <p className="text-sm font-heading text-gray-900 dark:text-gray-100">Akili Backend</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default FileUploader;
