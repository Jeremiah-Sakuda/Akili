import React, { useRef, useState } from 'react';
import { ingest, type IngestResponse } from '../api';

interface FileUploaderProps {
  onSuccess: (docId: string) => void;
  onBack?: () => void;
}

const FileUploader: React.FC<FileUploaderProps> = ({ onSuccess, onBack }) => {
  const inputRef = useRef<HTMLInputElement>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<IngestResponse | null>(null);
  const [copied, setCopied] = useState(false);

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
    try {
      const data = await ingest(file);
      setResult(data);
      onSuccess(data.doc_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Upload failed.');
    } finally {
      setLoading(false);
    }
  };

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
      className="flex-1 bg-slate-50 relative flex flex-col items-center justify-center p-8 overflow-hidden h-full"
      onDrop={handleDrop}
      onDragOver={(e) => e.preventDefault()}
    >
      <div
        className="absolute inset-0 z-0 opacity-[0.03] pointer-events-none"
        style={{
          backgroundImage:
            'linear-gradient(#000 1px, transparent 1px), linear-gradient(90deg, #000 1px, transparent 1px)',
          backgroundSize: '20px 20px',
        }}
      />

      <div className="w-full max-w-[640px] z-10 fade-in">
        {onBack && (
          <button
            type="button"
            onClick={onBack}
            className="mb-4 text-sm text-slate-500 hover:text-primary flex items-center gap-1"
          >
            <span className="material-symbols-outlined text-[18px]">arrow_back</span>
            Back
          </button>
        )}
        <div className="mb-8 text-center">
          <h2 className="text-2xl font-bold text-slate-800 tracking-tight">Upload Technical Document</h2>
          <p className="text-slate-500 mt-2 text-sm">Ingest PDFs for verification analysis</p>
        </div>

        <div
          className="group relative bg-white w-full rounded-xl border-2 border-dashed border-slate-300 hover:border-primary transition-all duration-200 cursor-pointer shadow-sm hover:shadow-md hover:bg-slate-50/50"
          onClick={() => inputRef.current?.click()}
          onKeyDown={(e) => e.key === 'Enter' && inputRef.current?.click()}
          role="button"
          tabIndex={0}
        >
          <input
            ref={inputRef}
            className="absolute inset-0 opacity-0 cursor-pointer z-10 w-full"
            type="file"
            accept=".pdf,application/pdf"
            multiple={false}
            onChange={handleChange}
            disabled={loading}
          />
          <div className="flex flex-col items-center justify-center h-80 p-6">
            {loading ? (
              <>
                <div className="size-16 rounded-full bg-primary/10 flex items-center justify-center mb-5 animate-pulse">
                  <span className="material-symbols-outlined text-[32px] text-primary">hourglass_empty</span>
                </div>
                <p className="text-lg font-semibold text-slate-800">Processing…</p>
                <p className="text-sm text-slate-400 mt-1">Extracting canonical facts from PDF</p>
              </>
            ) : (
              <>
                <div className="size-16 rounded-full bg-slate-100 group-hover:bg-primary/10 flex items-center justify-center mb-5 transition-colors duration-200">
                  <span className="material-symbols-outlined text-[32px] text-slate-400 group-hover:text-primary transition-colors duration-200">
                    cloud_upload
                  </span>
                </div>
                <p className="text-lg font-semibold text-slate-800 mb-1">Drag & drop a PDF here</p>
                <p className="text-sm text-slate-400 mb-6">
                  or <span className="text-primary font-medium hover:underline">browse your computer</span>
                </p>
                <div className="flex gap-2 text-xs text-slate-400 font-mono bg-slate-50 px-3 py-1.5 rounded border border-slate-100">
                  <span>SUPPORTED: PDF</span>
                </div>
              </>
            )}
          </div>
          <div className="absolute top-[-2px] left-[-2px] w-6 h-6 border-t-2 border-l-2 border-slate-300 group-hover:border-primary rounded-tl-lg transition-colors" />
          <div className="absolute top-[-2px] right-[-2px] w-6 h-6 border-t-2 border-r-2 border-slate-300 group-hover:border-primary rounded-tr-lg transition-colors" />
          <div className="absolute bottom-[-2px] left-[-2px] w-6 h-6 border-b-2 border-l-2 border-slate-300 group-hover:border-primary rounded-bl-lg transition-colors" />
          <div className="absolute bottom-[-2px] right-[-2px] w-6 h-6 border-b-2 border-r-2 border-slate-300 group-hover:border-primary rounded-br-lg transition-colors" />
        </div>

        {error && (
          <div className="mt-4 p-4 rounded-lg border border-amber-200 bg-amber-50 text-amber-800 text-sm">
            {error}
          </div>
        )}

        {result && !loading && (
          <div className="mt-6 p-4 rounded-lg border border-emerald-200 bg-emerald-50/50">
            <p className="text-sm font-semibold text-emerald-800 mb-2">Document canonicalized</p>
            <div className="flex items-center gap-2 mb-1">
              <p className="text-xs font-mono text-slate-600">
                <span className="text-slate-400">doc_id:</span> {result.doc_id}
              </p>
              <button
                type="button"
                onClick={copyDocId}
                className="p-1 rounded hover:bg-emerald-100 text-slate-500 hover:text-emerald-700 transition-colors"
                title="Copy doc_id"
              >
                <span className="material-symbols-outlined text-[16px]">
                  {copied ? 'check' : 'content_copy'}
                </span>
              </button>
            </div>
            <p className="text-xs text-slate-600">
              {result.units_count} units · {result.bijections_count} bijections · {result.grids_count} grids
            </p>
          </div>
        )}

        <div className="mt-8 grid grid-cols-2 gap-4">
          <div className="bg-white p-4 rounded-lg border border-slate-200 shadow-sm flex items-start gap-3">
            <div className="p-1.5 bg-green-50 rounded text-green-600">
              <span className="material-symbols-outlined text-[20px]">check_circle</span>
            </div>
            <div>
              <p className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-0.5">System Status</p>
              <p className="text-sm font-semibold text-slate-700">Ready for Ingest</p>
            </div>
          </div>
          <div className="bg-white p-4 rounded-lg border border-slate-200 shadow-sm flex items-start gap-3">
            <div className="p-1.5 bg-blue-50 rounded text-blue-600">
              <span className="material-symbols-outlined text-[20px]">auto_awesome</span>
            </div>
            <div>
              <p className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-0.5">API</p>
              <p className="text-sm font-semibold text-slate-700">Akili Backend</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default FileUploader;
