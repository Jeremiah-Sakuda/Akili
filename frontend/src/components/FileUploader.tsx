import React, { useCallback, useRef, useState } from 'react';
import { ingest, type IngestResponse } from '../api';

type UploadPhase =
  | 'idle'
  | 'uploading'
  | 'rendering'
  | 'extracting'
  | 'canonicalizing'
  | 'done'
  | 'error';

const PHASES: { key: UploadPhase; label: string; description: string }[] = [
  { key: 'uploading', label: 'Uploading file', description: 'Sending PDF to server' },
  { key: 'rendering', label: 'Rendering PDF pages', description: 'Converting pages to images (PyMuPDF)' },
  { key: 'extracting', label: 'Extracting with Gemini', description: 'Per-page vision extraction' },
  { key: 'canonicalizing', label: 'Canonicalizing', description: 'Normalizing and storing facts' },
  { key: 'done', label: 'Done', description: 'Document ready for verification' },
];

const PHASE_ORDER: UploadPhase[] = ['uploading', 'rendering', 'extracting', 'canonicalizing', 'done'];

interface FileUploaderProps {
  onSuccess: (docId: string) => void;
  onBack?: () => void;
}

const FileUploader: React.FC<FileUploaderProps> = ({ onSuccess, onBack }) => {
  const inputRef = useRef<HTMLInputElement>(null);
  const [loading, setLoading] = useState(false);
  const [phase, setPhase] = useState<UploadPhase>('idle');
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<IngestResponse | null>(null);
  const [copied, setCopied] = useState(false);
  const timersRef = useRef<ReturnType<typeof setTimeout>[]>([]);

  const clearPhaseTimers = useCallback(() => {
    timersRef.current.forEach((t) => clearTimeout(t));
    timersRef.current = [];
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

  const handleFile = async (files: FileList | null) => {
    if (!files?.length) return;
    const file = files[0];
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      setError('Please upload a PDF file.');
      return;
    }
    setError(null);
    setResult(null);
    setLoading(true);
    setPhase('uploading');

    // Advance phases on a timer so engineers see pipeline progress (server doesn't stream status)
    const t1 = setTimeout(() => setPhase('rendering'), 500);
    const t2 = setTimeout(() => setPhase('extracting'), 2000);
    const t3 = setTimeout(() => setPhase('canonicalizing'), 4500);
    timersRef.current = [t1, t2, t3];

    try {
      const data = await ingest(file);
      clearPhaseTimers();
      setPhase('done');
      setResult(data);
      onSuccess(data.doc_id);
    } catch (e) {
      clearPhaseTimers();
      setPhase('error');
      setError(e instanceof Error ? e.message : 'Upload failed.');
    } finally {
      setLoading(false);
    }
  };

  React.useEffect(() => {
    return () => clearPhaseTimers();
  }, [clearPhaseTimers]);

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    handleFile(e.dataTransfer.files);
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    handleFile(e.target.files);
    e.target.value = '';
  };

  return (
    <div
      className="flex-1 bg-white dark:bg-[#0d1117] relative flex flex-col items-center justify-center p-8 overflow-hidden h-full"
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
        <div className="mb-8 text-center">
          <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100 tracking-tight">Upload Technical Document</h2>
          <p className="text-gray-600 dark:text-gray-400 mt-2 text-sm">Ingest PDFs for verification analysis</p>
        </div>

        <div
          className="group relative bg-white dark:bg-[#161b22] w-full border-2 border-dashed border-gray-300 dark:border-[#30363d] hover:border-primary dark:hover:border-primary transition-colors cursor-pointer"
          onKeyDown={(e) => e.key === 'Enter' && inputRef.current?.click()}
          role="button"
          tabIndex={0}
        >
          <input
            ref={inputRef}
            className="absolute inset-0 opacity-0 cursor-pointer z-10 w-full"
            type="file"
            aria-label="Choose PDF file"
            accept=".pdf,application/pdf"
            multiple={false}
            onChange={handleChange}
            disabled={loading}
          />
          <div className="flex flex-col items-center justify-center min-h-64 p-6">
            {loading || phase === 'done' ? (
              <>
                <div className="size-12 bg-primary/10 dark:bg-primary/20 flex items-center justify-center mb-4">
                  <span className="material-symbols-outlined text-[24px] text-primary">
                    {phase === 'done' ? 'check_circle' : 'hourglass_empty'}
                  </span>
                </div>
                <p className="text-base font-medium text-gray-900 dark:text-gray-100">
                  {phase === 'done' ? 'Document ready' : `Phase: ${PHASES.find((p) => p.key === phase)?.label ?? phase}`}
                </p>
                <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                  {phase === 'done' ? 'Canonical facts stored' : PHASES.find((p) => p.key === phase)?.description ?? '…'}
                </p>
                {(loading || phase === 'done') && (
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
              </>
            ) : (
              <>
                <div className="size-12 bg-gray-100 dark:bg-[#0d1117] group-hover:bg-primary/10 dark:group-hover:bg-primary/20 flex items-center justify-center mb-4 transition-colors">
                  <span className="material-symbols-outlined text-[24px] text-gray-500 dark:text-gray-400 group-hover:text-primary transition-colors">
                    cloud_upload
                  </span>
                </div>
                <p className="text-base font-medium text-gray-900 dark:text-gray-100 mb-1">Drag & drop a PDF here</p>
                <p className="text-sm text-gray-600 dark:text-gray-400 mb-6">
                  or <span className="text-primary font-medium">browse your computer</span>
                </p>
                <div className="flex gap-2 text-xs text-gray-600 dark:text-gray-400 font-mono bg-gray-50 dark:bg-[#0d1117] px-3 py-1.5 border border-gray-200 dark:border-[#30363d]">
                  <span>SUPPORTED: PDF</span>
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

        {result && !loading && (
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
              {result.units_count} units · {result.bijections_count} bijections · {result.grids_count} grids
            </p>
          </div>
        )}

        <div className="mt-8 grid grid-cols-2 gap-4">
          <div className="bg-white dark:bg-[#161b22] p-4 border border-gray-200 dark:border-[#30363d] flex items-start gap-3">
            <div className="p-1.5 bg-emerald-50 dark:bg-emerald-900/30 text-emerald-600 dark:text-emerald-400">
              <span className="material-symbols-outlined text-[18px]">check_circle</span>
            </div>
            <div>
              <p className="text-[10px] font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-0.5">System Status</p>
              <p className="text-sm font-medium text-gray-900 dark:text-gray-100">Ready for Ingest</p>
            </div>
          </div>
          <div className="bg-white dark:bg-[#161b22] p-4 border border-gray-200 dark:border-[#30363d] flex items-start gap-3">
            <div className="p-1.5 bg-primary/10 dark:bg-primary/20 text-primary">
              <span className="material-symbols-outlined text-[18px]">api</span>
            </div>
            <div>
              <p className="text-[10px] font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-0.5">API</p>
              <p className="text-sm font-medium text-gray-900 dark:text-gray-100">Akili Backend</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default FileUploader;
