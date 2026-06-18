import type { BenchmarkRow } from './BenchmarkTable';

/**
 * ILLUSTRATIVE target numbers for the landing page.
 *
 * These are NOT measured results — they are placeholder targets shown only until
 * a real benchmark run produces `public/benchmark-results.json`. Generate measured
 * numbers with:
 *
 *   GOOGLE_API_KEY=... python benchmark/run_benchmark.py
 *
 * (with datasheet PDFs in `benchmark/fixtures/<chip>.pdf`). The runner writes
 * `frontend/public/benchmark-results.json`, which `loadBenchmarkResults()` then
 * surfaces as measured data.
 */
export const ILLUSTRATIVE_BENCHMARK_DATA: BenchmarkRow[] = [
  { chip: 'ATmega328P', akiliAccuracy: 92, geminiAccuracy: 74, hallucinationDelta: 18 },
  { chip: 'ESP32', akiliAccuracy: 88, geminiAccuracy: 71, hallucinationDelta: 17 },
  { chip: 'STM32F103', akiliAccuracy: 85, geminiAccuracy: 68, hallucinationDelta: 17 },
  { chip: 'NE555', akiliAccuracy: 94, geminiAccuracy: 82, hallucinationDelta: 12 },
  { chip: 'LM7805', akiliAccuracy: 91, geminiAccuracy: 79, hallucinationDelta: 12 },
];

/** @deprecated use ILLUSTRATIVE_BENCHMARK_DATA. Kept for backwards compatibility. */
export const DEFAULT_BENCHMARK_DATA = ILLUSTRATIVE_BENCHMARK_DATA;

export interface BenchmarkResults {
  rows: BenchmarkRow[];
  /** true only when rows came from an actual benchmark run. */
  measured: boolean;
  generatedAt?: string;
}

/**
 * Load measured benchmark results if a run has published them; otherwise fall
 * back to the clearly-labeled illustrative targets.
 */
export async function loadBenchmarkResults(): Promise<BenchmarkResults> {
  try {
    const res = await fetch('/benchmark-results.json', { cache: 'no-store' });
    if (res.ok) {
      const data = await res.json();
      if (Array.isArray(data?.rows) && data.rows.length > 0) {
        return { rows: data.rows as BenchmarkRow[], measured: true, generatedAt: data.generated_at };
      }
    }
  } catch {
    // No measured results available — fall through to illustrative data.
  }
  return { rows: ILLUSTRATIVE_BENCHMARK_DATA, measured: false };
}
