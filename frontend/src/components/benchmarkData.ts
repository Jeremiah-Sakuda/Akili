import type { BenchmarkRow } from './BenchmarkTable';

/**
 * Default benchmark data for landing page.
 * TODO: Replace with dynamic data from /api/benchmark endpoint
 */
export const DEFAULT_BENCHMARK_DATA: BenchmarkRow[] = [
  { chip: 'ATmega328P', akiliAccuracy: 92, geminiAccuracy: 74, hallucinationDelta: 18 },
  { chip: 'ESP32', akiliAccuracy: 88, geminiAccuracy: 71, hallucinationDelta: 17 },
  { chip: 'STM32F103', akiliAccuracy: 85, geminiAccuracy: 68, hallucinationDelta: 17 },
  { chip: 'NE555', akiliAccuracy: 94, geminiAccuracy: 82, hallucinationDelta: 12 },
  { chip: 'LM7805', akiliAccuracy: 91, geminiAccuracy: 79, hallucinationDelta: 12 },
];
