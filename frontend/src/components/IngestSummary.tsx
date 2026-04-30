import React from 'react';
import type { IngestResponse } from '../api';

interface IngestSummaryProps {
  result: IngestResponse;
  onDismiss: () => void;
}

const IngestSummary: React.FC<IngestSummaryProps> = ({ result, onDismiss }) => {
  const totalFacts = (result.units_count ?? 0) + (result.bijections_count ?? 0) + (result.grids_count ?? 0);
  const hasWarning = !!result.extraction_warning;
  const hasNote = !!result.extraction_note;

  return (
    <div className="animate-in mx-auto max-w-lg w-full p-4 bg-white dark:bg-[#161b22] border border-gray-200 dark:border-[#30363d] rounded-xl shadow-sm">
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-heading text-sm text-gray-900 dark:text-gray-100">Ingest Summary</h3>
        <button
          type="button"
          onClick={onDismiss}
          className="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
          aria-label="Dismiss summary"
        >
          <span className="material-symbols-outlined text-[16px]">close</span>
        </button>
      </div>

      <div className="grid grid-cols-3 gap-3 mb-3">
        <div className="text-center p-3 bg-gray-50 dark:bg-[#0d1117] rounded-lg">
          <p className="text-lg font-heading text-primary">{result.units_count ?? 0}</p>
          <p className="text-[10px] text-gray-500 dark:text-gray-400 uppercase tracking-wider">Units</p>
        </div>
        <div className="text-center p-3 bg-gray-50 dark:bg-[#0d1117] rounded-lg">
          <p className="text-lg font-heading text-primary">{result.bijections_count ?? 0}</p>
          <p className="text-[10px] text-gray-500 dark:text-gray-400 uppercase tracking-wider">Bijections</p>
        </div>
        <div className="text-center p-3 bg-gray-50 dark:bg-[#0d1117] rounded-lg">
          <p className="text-lg font-heading text-primary">{result.grids_count ?? 0}</p>
          <p className="text-[10px] text-gray-500 dark:text-gray-400 uppercase tracking-wider">Grids</p>
        </div>
      </div>

      <div className="text-xs font-mono text-gray-600 dark:text-gray-400 space-y-1">
        <p>{result.page_count} page(s) processed · {totalFacts} canonical facts extracted</p>
        {result.pages_failed != null && result.pages_failed > 0 && (
          <p className="text-amber-600 dark:text-amber-400">
            {result.pages_failed} page(s) skipped
          </p>
        )}
      </div>

      {hasWarning && (
        <div className="mt-3 p-2 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded text-xs text-amber-700 dark:text-amber-300" role="alert">
          {result.extraction_warning}
        </div>
      )}

      {hasNote && (
        <div className="mt-3 p-2 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded text-xs text-blue-700 dark:text-blue-300" role="status">
          {result.extraction_note}
        </div>
      )}
    </div>
  );
};

export default IngestSummary;
