/**
 * API client for Akili FastAPI backend.
 * In dev, Vite proxy forwards /api/* to the backend (see vite.config.ts).
 * When Firebase auth is configured and user is signed in, sends Bearer token for API auth.
 * On 401, signs out from Firebase and throws so the UI shows the login page.
 */

import { signOut } from 'firebase/auth';
import { getFirebaseAuth } from './firebase';

const API_BASE = import.meta.env.VITE_API_URL || '/api';

/** On 401, sign out from Firebase and throw; AuthContext will show login. */
async function handle401(res: Response): Promise<void> {
  if (res.status === 401) {
    const auth = getFirebaseAuth();
    if (auth) await signOut(auth);
    throw new Error('Session expired. Please sign in again.');
  }
}

async function authHeaders(init?: HeadersInit): Promise<HeadersInit> {
  const headers = new Headers(init);
  const auth = getFirebaseAuth();
  if (auth?.currentUser) {
    try {
      const token = await auth.currentUser.getIdToken();
      if (token) headers.set('Authorization', `Bearer ${token}`);
    } catch {
      // ignore token errors
    }
  }
  return headers;
}

export interface DocumentSummary {
  doc_id: string;
  filename: string;
  page_count: number;
  created_at: string;
  units_count: number;
  bijections_count: number;
  grids_count: number;
}

export interface IngestResponse {
  doc_id: string;
  filename: string;
  page_count: number;
  units_count: number;
  bijections_count: number;
  grids_count: number;
  /** Number of pages that failed extraction (e.g. rate limit); 0 if all succeeded */
  pages_failed?: number;
  /** Present when no facts were extracted; suggests checking API key and server logs */
  extraction_warning?: string;
  /** Present when some pages were skipped (e.g. rate limits); suggests increasing delay */
  extraction_note?: string;
}

export interface ProofPointBBox {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

export interface ProofPoint {
  x: number;
  y: number;
  page?: number;
  bbox?: ProofPointBBox | null;
  source_id?: string | null;
  source_type?: string | null;
}

/** Indicates whether the response text is the raw verified output or was rephrased by an LLM */
export type FormattingSource = 'verified_raw' | 'gemini_rephrase';

export type ConfidenceTier = 'verified' | 'review' | 'refused';

export interface ConfidenceScore {
  extraction_agreement: number;
  canonical_validation: number;
  verification_strength: number;
  overall: number;
}

export interface AnswerWithProof {
  status: 'answer';
  answer: string;
  proof: ProofPoint[];
  source_id?: string | null;
  source_type?: string | null;
  /** When requested (include_formatted_answer), 1-sentence natural-language phrasing from Gemini; null on failure or timeout. */
  formatted_answer?: string | null;
  formatting_source?: FormattingSource;
  confidence?: ConfidenceScore | null;
  confidence_tier?: ConfidenceTier;
}

export interface Refuse {
  status: 'refuse';
  reason: string;
  formatting_source?: FormattingSource;
}

export type QueryResponse = AnswerWithProof | Refuse;

/** Single message in the verification chat */
export interface ChatMessage {
  role: 'user' | 'assistant';
  text: string;
  /** For assistant: full API response (proof, refuse reason, etc.); null when loading */
  response?: QueryResponse | null;
}

export async function getDocuments(): Promise<DocumentSummary[]> {
  const res = await fetch(`${API_BASE}/documents`, { headers: await authHeaders() });
  if (!res.ok) {
    await handle401(res);
    throw new Error('Failed to fetch documents');
  }
  const data = await res.json();
  return data.documents ?? [];
}

export async function deleteDocument(docId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/documents/${encodeURIComponent(docId)}`, {
    method: 'DELETE',
    headers: await authHeaders(),
  });
  if (!res.ok) {
    await handle401(res);
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    const detail = err.detail;
    const message = Array.isArray(detail) ? detail.join(' ') : detail ?? 'Delete failed';
    throw new Error(message);
  }
}

export async function ingest(file: File): Promise<IngestResponse> {
  const form = new FormData();
  form.append('file', file);
  const res = await fetch(`${API_BASE}/ingest`, {
    method: 'POST',
    headers: await authHeaders(),
    body: form,
  });
  if (!res.ok) {
    await handle401(res);
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    const detail = err.detail;
    const message = Array.isArray(detail) ? detail.join(' ') : detail ?? 'Ingest failed';
    console.error('[Akili ingest]', res.status, message);
    throw new Error(message);
  }
  return res.json();
}

/** Server-sent progress event from POST /ingest/stream */
export interface IngestProgressEvent {
  phase: 'rendering' | 'rendering_done' | 'extracting' | 'canonicalizing' | 'storing' | 'done' | 'error';
  total_pages?: number;
  page?: number;
  doc_id?: string;
  filename?: string;
  page_count?: number;
  units_count?: number;
  bijections_count?: number;
  grids_count?: number;
  pages_failed?: number;
  extraction_warning?: string;
  extraction_note?: string;
  message?: string;
}

/**
 * Upload a PDF and run ingestion with server-sent progress.
 * Calls onProgress for each event; returns final IngestResponse on "done", throws on "error".
 */
export async function ingestStream(
  file: File,
  onProgress: (event: IngestProgressEvent) => void
): Promise<IngestResponse> {
  const form = new FormData();
  form.append('file', file);
  const headers = await authHeaders();
  const res = await fetch(`${API_BASE}/ingest/stream`, {
    method: 'POST',
    headers,
    body: form,
  });
  if (!res.ok) {
    await handle401(res);
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    const detail = err.detail;
    const message = Array.isArray(detail) ? detail.join(' ') : detail ?? 'Ingest failed';
    throw new Error(message);
  }
  const reader = res.body?.getReader();
  if (!reader) throw new Error('No response body');
  const decoder = new TextDecoder();
  let buffer = '';
  let result: IngestResponse | null = null;
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const events = buffer.split('\n\n');
    buffer = events.pop() ?? '';
    for (const event of events) {
      const dataLine = event.split('\n').find((l) => l.startsWith('data: '));
      if (!dataLine) continue;
      try {
        const msg = JSON.parse(dataLine.slice(6)) as IngestProgressEvent;
        onProgress(msg);
        if (msg.phase === 'done') {
          result = {
            doc_id: msg.doc_id!,
            filename: msg.filename ?? 'upload.pdf',
            page_count: msg.page_count ?? msg.total_pages ?? 0,
            units_count: msg.units_count ?? 0,
            bijections_count: msg.bijections_count ?? 0,
            grids_count: msg.grids_count ?? 0,
            pages_failed: msg.pages_failed,
            extraction_warning: msg.extraction_warning,
            extraction_note: msg.extraction_note,
          };
        }
        if (msg.phase === 'error') {
          throw new Error(msg.message ?? 'Ingest failed');
        }
      } catch (e) {
        if (e instanceof SyntaxError) continue;
        throw e;
      }
    }
  }
  if (!result) throw new Error('Ingest stream ended without done event');
  return result;
}

export async function query(
  docId: string,
  question: string,
  options?: { includeFormattedAnswer?: boolean }
): Promise<QueryResponse> {
  const headers = await authHeaders({ 'Content-Type': 'application/json' });
  const res = await fetch(`${API_BASE}/query`, {
    method: 'POST',
    headers,
    body: JSON.stringify({
      doc_id: docId,
      question,
      include_formatted_answer: options?.includeFormattedAnswer ?? false,
    }),
  });
  if (!res.ok) {
    await handle401(res);
    throw new Error('Query failed');
  }
  return res.json();
}

export function isRefuse(r: QueryResponse): r is Refuse {
  return r.status === 'refuse';
}

export function isAnswer(r: QueryResponse): r is AnswerWithProof {
  return r.status === 'answer';
}

export interface CanonicalUnit {
  type: 'unit';
  id: string | null;
  label: string | null;
  value: unknown;
  unit_of_measure: string | null;
  origin: { x: number; y: number };
  page: number;
}

export interface CanonicalBijection {
  type: 'bijection';
  id: string | null;
  mapping: Record<string, string>;
  origin: { x: number; y: number };
  page: number;
}

export interface CanonicalGrid {
  type: 'grid';
  id: string | null;
  rows: number;
  cols: number;
  cells_count: number;
  origin: { x: number; y: number };
  page: number;
}

export interface CanonicalResponse {
  doc_id: string;
  units: CanonicalUnit[];
  bijections: CanonicalBijection[];
  grids: CanonicalGrid[];
}

export async function getCanonical(docId: string): Promise<CanonicalResponse> {
  const res = await fetch(`${API_BASE}/documents/${encodeURIComponent(docId)}/canonical`, {
    headers: await authHeaders(),
  });
  if (!res.ok) {
    await handle401(res);
    throw new Error('Failed to fetch canonical');
  }
  return res.json();
}

/** Fetch PDF file for a document (for viewer / Show on document). Returns blob URL; caller must revoke when done. */
export async function getDocumentFile(docId: string): Promise<string> {
  const res = await fetch(`${API_BASE}/documents/${encodeURIComponent(docId)}/file`, {
    headers: await authHeaders(),
  });
  if (!res.ok) {
    await handle401(res);
    throw new Error('Failed to fetch document file');
  }
  const blob = await res.blob();
  return URL.createObjectURL(blob);
}

// ---------------------------------------------------------------------------
// Free Tier Usage
// ---------------------------------------------------------------------------

export interface UsageBucket {
  used: number;
  limit: number;
  remaining: number;
}

export interface UsageSummary {
  documents: UsageBucket;
  queries: UsageBucket;
}

export async function getUsage(): Promise<UsageSummary> {
  const res = await fetch(`${API_BASE}/usage`, {
    headers: await authHeaders(),
  });
  if (!res.ok) {
    await handle401(res);
    throw new Error('Failed to fetch usage');
  }
  return res.json();
}

// ---------------------------------------------------------------------------
// Corrections / Human-in-the-Loop Review
// ---------------------------------------------------------------------------

export interface CorrectionRecord {
  id: number;
  canonical_id: string;
  canonical_type: string;
  action: 'confirm' | 'correct';
  original_value: string;
  corrected_value: string | null;
  corrected_by: string | null;
  notes: string | null;
  created_at: string | null;
}

export interface CorrectionStats {
  total: number;
  confirmations: number;
  corrections: number;
  correction_rate: number;
}

export interface SubmitCorrectionRequest {
  doc_id: string;
  canonical_id: string;
  canonical_type: string;
  action: 'confirm' | 'correct';
  original_value: string;
  corrected_value?: string;
  notes?: string;
}

export async function submitCorrection(req: SubmitCorrectionRequest): Promise<{ correction_id: number }> {
  const headers = await authHeaders({ 'Content-Type': 'application/json' });
  const res = await fetch(`${API_BASE}/corrections`, {
    method: 'POST',
    headers,
    body: JSON.stringify(req),
  });
  if (!res.ok) {
    await handle401(res);
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? 'Failed to submit correction');
  }
  return res.json();
}

export async function getCorrections(docId: string): Promise<CorrectionRecord[]> {
  const res = await fetch(`${API_BASE}/corrections/${encodeURIComponent(docId)}`, {
    headers: await authHeaders(),
  });
  if (!res.ok) {
    await handle401(res);
    throw new Error('Failed to fetch corrections');
  }
  const data = await res.json();
  return data.corrections ?? [];
}

export async function getCorrectionStats(docId: string): Promise<CorrectionStats> {
  const res = await fetch(`${API_BASE}/corrections/stats/${encodeURIComponent(docId)}`, {
    headers: await authHeaders(),
  });
  if (!res.ok) {
    await handle401(res);
    throw new Error('Failed to fetch correction stats');
  }
  return res.json();
}

// ---------------------------------------------------------------------------
// C3: Cross-Document Comparison
// ---------------------------------------------------------------------------

export interface ComparisonRow {
  doc_id: string;
  doc_name: string;
  value: number | string | null;
  unit_of_measure: string | null;
  source_unit_id: string | null;
  page: number | null;
}

export interface ComparisonParameter {
  parameter: string;
  direction: string;
  best_doc_id: string | null;
  best_value: number | string | null;
  summary: string;
  rows: ComparisonRow[];
}

export interface ComparisonResponse {
  comparisons: ComparisonParameter[];
}

export async function compareDocuments(
  docIds: string[],
  question: string,
): Promise<ComparisonResponse> {
  const headers = await authHeaders({ 'Content-Type': 'application/json' });
  const res = await fetch(`${API_BASE}/compare`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ doc_ids: docIds, question }),
  });
  if (!res.ok) {
    await handle401(res);
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? 'Failed to compare documents');
  }
  return res.json();
}

// ---------------------------------------------------------------------------
// C4: Correction Patterns / Learning
// ---------------------------------------------------------------------------

export interface PatternStats {
  total_patterns: number;
  auto_correctable: number;
  reliable_patterns: number;
  categories: Record<string, number>;
  top_patterns: Array<{
    id: string;
    description: string;
    occurrences: number;
    auto_correctable: boolean;
  }>;
}

export async function getPatternStats(): Promise<PatternStats> {
  const res = await fetch(`${API_BASE}/patterns`, {
    headers: await authHeaders(),
  });
  if (!res.ok) {
    await handle401(res);
    throw new Error('Failed to fetch patterns');
  }
  return res.json();
}

export interface CorrectionSuggestion {
  original_value: string;
  suggested_correction: string | null;
  has_suggestion: boolean;
}

export async function suggestCorrection(
  canonicalType: string,
  originalValue: string,
): Promise<CorrectionSuggestion> {
  const headers = await authHeaders({ 'Content-Type': 'application/json' });
  const res = await fetch(`${API_BASE}/patterns/suggest`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ canonical_type: canonicalType, original_value: originalValue }),
  });
  if (!res.ok) {
    await handle401(res);
    throw new Error('Failed to get suggestion');
  }
  return res.json();
}
