import React, { useState } from 'react';
import { compareDocuments, ComparisonResponse, ComparisonParameter } from '../api';

interface CompareViewProps {
  documents: Array<{ doc_id: string; filename: string }>;
}

const CompareView: React.FC<CompareViewProps> = ({ documents }) => {
  const [selectedDocs, setSelectedDocs] = useState<string[]>([]);
  const [question, setQuestion] = useState('');
  const [result, setResult] = useState<ComparisonResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const toggleDoc = (docId: string) => {
    setSelectedDocs((prev) =>
      prev.includes(docId) ? prev.filter((d) => d !== docId) : [...prev, docId]
    );
  };

  const handleCompare = async () => {
    if (selectedDocs.length < 2) {
      setError('Select at least 2 documents to compare');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const data = await compareDocuments(selectedDocs, question || 'Compare all parameters');
      setResult(data);
    } catch (e: any) {
      setError(e.message || 'Comparison failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-4 space-y-4">
      <h2 className="text-lg font-semibold text-zinc-100">Cross-Document Comparison</h2>

      <div className="space-y-2">
        <p className="text-sm text-zinc-400">Select documents to compare:</p>
        <div className="flex flex-wrap gap-2">
          {documents.map((doc) => (
            <button
              key={doc.doc_id}
              onClick={() => toggleDoc(doc.doc_id)}
              className={`px-3 py-1.5 rounded text-sm transition ${
                selectedDocs.includes(doc.doc_id)
                  ? 'bg-blue-600 text-white'
                  : 'bg-zinc-700 text-zinc-300 hover:bg-zinc-600'
              }`}
            >
              {doc.filename || doc.doc_id.slice(0, 8)}
            </button>
          ))}
        </div>
      </div>

      <div className="flex gap-2">
        <input
          type="text"
          placeholder="e.g. Compare max voltage (or leave blank for all)"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          className="flex-1 px-3 py-2 bg-zinc-800 border border-zinc-600 rounded text-sm text-zinc-100 placeholder-zinc-500"
        />
        <button
          onClick={handleCompare}
          disabled={loading || selectedDocs.length < 2}
          className="px-4 py-2 bg-blue-600 text-white rounded text-sm font-medium disabled:opacity-50 hover:bg-blue-500 transition"
        >
          {loading ? 'Comparing...' : 'Compare'}
        </button>
      </div>

      {error && <p className="text-red-400 text-sm">{error}</p>}

      {result && (
        <div className="space-y-4">
          {result.comparisons.map((comp, i) => (
            <ComparisonTable key={i} comparison={comp} />
          ))}
        </div>
      )}
    </div>
  );
};

const ComparisonTable: React.FC<{ comparison: ComparisonParameter }> = ({ comparison }) => {
  const directionIcon = comparison.direction === 'lower' ? '↓' : comparison.direction === 'higher' ? '↑' : '–';

  return (
    <div className="bg-zinc-800 rounded-lg border border-zinc-700 overflow-hidden">
      <div className="px-4 py-2 bg-zinc-750 border-b border-zinc-700 flex items-center gap-2">
        <span className="text-sm font-medium text-zinc-100">{comparison.parameter}</span>
        <span className="text-xs text-zinc-400">({directionIcon} {comparison.direction} is better)</span>
      </div>

      {comparison.summary && (
        <div className="px-4 py-2 text-xs text-zinc-400 border-b border-zinc-700/50">
          {comparison.summary}
        </div>
      )}

      <table className="w-full text-sm">
        <thead>
          <tr className="text-zinc-400 text-xs">
            <th className="text-left px-4 py-2 font-medium">Document</th>
            <th className="text-right px-4 py-2 font-medium">Value</th>
            <th className="text-right px-4 py-2 font-medium">Unit</th>
            <th className="text-right px-4 py-2 font-medium">Page</th>
          </tr>
        </thead>
        <tbody>
          {comparison.rows.map((row, i) => {
            const isBest = row.doc_id === comparison.best_doc_id;
            return (
              <tr
                key={i}
                className={`border-t border-zinc-700/50 ${isBest ? 'bg-green-900/20' : ''}`}
              >
                <td className="px-4 py-2 text-zinc-200">
                  {row.doc_name}
                  {isBest && <span className="ml-2 text-green-400 text-xs font-medium">★ Best</span>}
                </td>
                <td className="px-4 py-2 text-right text-zinc-100 font-mono">
                  {row.value !== null ? String(row.value) : '—'}
                </td>
                <td className="px-4 py-2 text-right text-zinc-400">
                  {row.unit_of_measure || '—'}
                </td>
                <td className="px-4 py-2 text-right text-zinc-400">
                  {row.page !== null ? row.page + 1 : '—'}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};

export default CompareView;
