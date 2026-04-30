import React from 'react';

export interface BenchmarkRow {
  chip: string;
  akiliAccuracy: number;
  geminiAccuracy: number;
  hallucinationDelta: number;
}

interface BenchmarkTableProps {
  data: BenchmarkRow[];
  compact?: boolean;
}

/**
 * Benchmark comparison table showing AKILI vs Gemini accuracy.
 * FR-ON-1, FR-ON-2: Display benchmark above the fold on landing page.
 */
export const BenchmarkTable: React.FC<BenchmarkTableProps> = ({ data, compact = false }) => {
  const overallAkili = Math.round(data.reduce((sum, r) => sum + r.akiliAccuracy, 0) / data.length);
  const overallGemini = Math.round(data.reduce((sum, r) => sum + r.geminiAccuracy, 0) / data.length);
  const overallDelta = overallAkili - overallGemini;

  return (
    <div className={`border border-white/10 rounded-lg bg-[#161d2e] overflow-hidden ${compact ? '' : 'shadow-lg'}`}>
      {/* Header */}
      <div className="px-4 py-3 border-b border-white/6 bg-[#0066CC]/5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="material-symbols-outlined text-[16px] text-[#0066CC]">analytics</span>
            <span className="text-sm font-semibold text-white">Accuracy Benchmark</span>
          </div>
          <span className="text-xs font-mono text-[#8b95a8]">50 questions across 5 chips</span>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-white/6">
              <th className="px-4 py-3 text-left font-medium text-[#8b95a8]">Chip</th>
              <th className="px-4 py-3 text-right font-medium text-[#0066CC]">AKILI</th>
              <th className="px-4 py-3 text-right font-medium text-[#8b95a8]">Gemini</th>
              <th className="px-4 py-3 text-right font-medium text-[#8b95a8]">
                <span className="hidden sm:inline">Halluc. Reduction</span>
                <span className="sm:hidden">Delta</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {data.map((row) => (
              <tr key={row.chip} className="border-b border-white/4 hover:bg-white/2 transition-colors">
                <td className="px-4 py-2.5 font-mono text-xs">{row.chip}</td>
                <td className="px-4 py-2.5 text-right">
                  <span className="inline-flex items-center gap-1">
                    <span className="font-semibold text-[#2DA66A]">{row.akiliAccuracy}%</span>
                  </span>
                </td>
                <td className="px-4 py-2.5 text-right text-[#8b95a8]">{row.geminiAccuracy}%</td>
                <td className="px-4 py-2.5 text-right">
                  <DeltaBadge delta={row.hallucinationDelta} />
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="bg-white/2">
              <td className="px-4 py-3 font-semibold">Overall</td>
              <td className="px-4 py-3 text-right font-bold text-[#2DA66A]">{overallAkili}%</td>
              <td className="px-4 py-3 text-right font-medium text-[#8b95a8]">{overallGemini}%</td>
              <td className="px-4 py-3 text-right">
                <DeltaBadge delta={overallDelta} large />
              </td>
            </tr>
          </tfoot>
        </table>
      </div>

      {/* Footer */}
      <div className="px-4 py-2.5 border-t border-white/6 bg-black/20">
        <p className="text-xs text-[#8b95a8] text-center">
          AKILI's verification engine reduces hallucinations by grounding answers in coordinate-level proof.
        </p>
      </div>
    </div>
  );
};

/**
 * Badge showing accuracy delta with color coding.
 */
const DeltaBadge: React.FC<{ delta: number; large?: boolean }> = ({ delta, large = false }) => {
  const isPositive = delta > 0;
  const colorClass = isPositive ? 'text-[#2DA66A] bg-[#2DA66A]/10' : 'text-[#D44040] bg-[#D44040]/10';

  return (
    <span className={`inline-flex items-center gap-0.5 px-2 py-0.5 rounded ${colorClass} ${large ? 'font-bold' : 'font-medium'}`}>
      {isPositive ? '+' : ''}{delta}%
      <span className={`material-symbols-outlined ${large ? 'text-[14px]' : 'text-[12px]'}`}>
        {isPositive ? 'arrow_upward' : 'arrow_downward'}
      </span>
    </span>
  );
};

export default BenchmarkTable;
