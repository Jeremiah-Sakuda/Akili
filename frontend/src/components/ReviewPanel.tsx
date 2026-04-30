import React, { useCallback, useEffect, useState } from 'react';
import {
  CorrectionRecord,
  CorrectionStats,
  getCorrections,
  getCorrectionStats,
  submitCorrection,
} from '../api';

interface ReviewPanelProps {
  docId: string;
  canonicalId?: string;
  canonicalType?: string;
  originalValue?: string;
  confidenceTier?: 'verified' | 'review' | 'refused';
  onCorrectionSubmitted?: () => void;
}

const ReviewPanel: React.FC<ReviewPanelProps> = ({
  docId,
  canonicalId,
  canonicalType,
  originalValue,
  confidenceTier,
  onCorrectionSubmitted,
}) => {
  const [corrections, setCorrections] = useState<CorrectionRecord[]>([]);
  const [stats, setStats] = useState<CorrectionStats | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [action, setAction] = useState<'confirm' | 'correct'>('confirm');
  const [correctedValue, setCorrectedValue] = useState('');
  const [notes, setNotes] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    try {
      const [c, s] = await Promise.all([
        getCorrections(docId),
        getCorrectionStats(docId),
      ]);
      setCorrections(c);
      setStats(s);
    } catch {
      // silent
    }
  }, [docId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleSubmit = async () => {
    if (!canonicalId || !canonicalType || !originalValue) return;
    if (action === 'correct' && !correctedValue.trim()) {
      setError('Please provide the corrected value');
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await submitCorrection({
        doc_id: docId,
        canonical_id: canonicalId,
        canonical_type: canonicalType,
        action,
        original_value: originalValue,
        corrected_value: action === 'correct' ? correctedValue.trim() : undefined,
        notes: notes.trim() || undefined,
      });
      setCorrectedValue('');
      setNotes('');
      setShowForm(false);
      loadData();
      onCorrectionSubmitted?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to submit');
    } finally {
      setSubmitting(false);
    }
  };

  const tierColor = {
    verified: 'text-green-600 dark:text-green-400',
    review: 'text-yellow-600 dark:text-yellow-400',
    refused: 'text-red-600 dark:text-red-400',
  };

  return (
    <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg">
      {/* Header */}
      <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="material-symbols-outlined text-[18px] text-gray-500">rate_review</span>
          <h3 className="text-sm font-semibold text-gray-800 dark:text-gray-200">Review & Corrections</h3>
        </div>
        {stats && (
          <div className="flex items-center gap-3 text-xs text-gray-500 dark:text-gray-400">
            <span>{stats.total} total</span>
            <span className="text-green-600 dark:text-green-400">{stats.confirmations} confirmed</span>
            <span className="text-blue-600 dark:text-blue-400">{stats.corrections} corrected</span>
          </div>
        )}
      </div>

      {/* Inline correction form for a specific fact */}
      {canonicalId && confidenceTier === 'review' && (
        <div className="px-4 py-3 border-b border-yellow-200 dark:border-yellow-800 bg-yellow-50 dark:bg-yellow-900/20">
          <div className="flex items-center gap-2 mb-2">
            <span className={`text-xs font-medium ${tierColor[confidenceTier]}`}>
              NEEDS REVIEW
            </span>
            <span className="text-xs text-gray-500">{canonicalType} &middot; {canonicalId}</span>
          </div>
          <p className="text-sm text-gray-700 dark:text-gray-300 mb-2">
            Original: <span className="font-mono bg-gray-100 dark:bg-gray-700 px-1 rounded">{originalValue}</span>
          </p>
          {!showForm ? (
            <div className="flex gap-2">
              <button
                onClick={() => { setAction('confirm'); setShowForm(true); }}
                className="px-3 py-1.5 text-xs font-medium rounded bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300 hover:bg-green-200 dark:hover:bg-green-900/50 transition-colors"
              >
                Confirm Correct
              </button>
              <button
                onClick={() => { setAction('correct'); setShowForm(true); }}
                className="px-3 py-1.5 text-xs font-medium rounded bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 hover:bg-blue-200 dark:hover:bg-blue-900/50 transition-colors"
              >
                Provide Correction
              </button>
            </div>
          ) : (
            <div className="space-y-2">
              {action === 'correct' && (
                <input
                  type="text"
                  value={correctedValue}
                  onChange={(e) => setCorrectedValue(e.target.value)}
                  placeholder="Enter the correct value..."
                  className="w-full px-3 py-1.5 text-sm rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-800 dark:text-gray-200 focus:ring-2 focus:ring-blue-400 outline-none"
                />
              )}
              <input
                type="text"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Optional notes..."
                className="w-full px-3 py-1.5 text-sm rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-800 dark:text-gray-200 focus:ring-2 focus:ring-blue-400 outline-none"
              />
              {error && <p className="text-xs text-red-500">{error}</p>}
              <div className="flex gap-2">
                <button
                  onClick={handleSubmit}
                  disabled={submitting}
                  className="px-3 py-1.5 text-xs font-medium rounded bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 transition-colors"
                >
                  {submitting ? 'Submitting...' : action === 'confirm' ? 'Confirm' : 'Submit Correction'}
                </button>
                <button
                  onClick={() => { setShowForm(false); setError(null); }}
                  className="px-3 py-1.5 text-xs font-medium rounded text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Correction history */}
      <div className="max-h-60 overflow-y-auto">
        {corrections.length === 0 ? (
          <p className="px-4 py-3 text-xs text-gray-400 dark:text-gray-500 italic">
            No corrections recorded yet
          </p>
        ) : (
          corrections.map((c) => (
            <div
              key={c.id}
              className="px-4 py-2.5 border-b last:border-b-0 border-gray-100 dark:border-gray-700/50 hover:bg-gray-50 dark:hover:bg-gray-700/30"
            >
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-2">
                  <span
                    className={`inline-block w-2 h-2 rounded-full ${
                      c.action === 'confirm' ? 'bg-green-500' : 'bg-blue-500'
                    }`}
                  />
                  <span className="text-xs font-medium text-gray-700 dark:text-gray-300">
                    {c.action === 'confirm' ? 'Confirmed' : 'Corrected'}
                  </span>
                  <span className="text-xs text-gray-400">{c.canonical_type} &middot; {c.canonical_id}</span>
                </div>
                <span className="text-xs text-gray-400">{c.created_at?.split('T')[0] ?? ''}</span>
              </div>
              <div className="text-xs text-gray-600 dark:text-gray-400">
                <span className="font-mono">{c.original_value}</span>
                {c.corrected_value && (
                  <>
                    <span className="mx-1">&rarr;</span>
                    <span className="font-mono text-blue-600 dark:text-blue-400">{c.corrected_value}</span>
                  </>
                )}
              </div>
              {c.notes && (
                <p className="text-xs text-gray-400 dark:text-gray-500 mt-0.5 italic">{c.notes}</p>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
};

export default ReviewPanel;
