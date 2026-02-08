/**
 * API client for Akili FastAPI backend.
 * In dev, Vite proxy forwards /api/* to the backend (see vite.config.ts).
 * When Firebase auth is configured and user is signed in, sends Bearer token for API auth.
 */

import { getFirebaseAuth } from './firebase';

const API_BASE = '/api';

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

export interface AnswerWithProof {
  status: 'answer';
  answer: string;
  proof: ProofPoint[];
  source_id?: string | null;
  source_type?: string | null;
  /** When requested (include_formatted_answer), 1-sentence natural-language phrasing from Gemini; null on failure or timeout. */
  formatted_answer?: string | null;
}

export interface Refuse {
  status: 'refuse';
  reason: string;
}

export type QueryResponse = AnswerWithProof | Refuse;

export async function getDocuments(): Promise<DocumentSummary[]> {
  const res = await fetch(`${API_BASE}/documents`, { headers: await authHeaders() });
  if (!res.ok) throw new Error('Failed to fetch documents');
  const data = await res.json();
  return data.documents ?? [];
}

export async function deleteDocument(docId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/documents/${encodeURIComponent(docId)}`, {
    method: 'DELETE',
    headers: await authHeaders(),
  });
  if (!res.ok) {
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
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    const detail = err.detail;
    const message = Array.isArray(detail) ? detail.join(' ') : detail ?? 'Ingest failed';
    console.error('[Akili ingest]', res.status, message);
    throw new Error(message);
  }
  return res.json();
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
      include_formatted_answer: options?.includeFormattedAnswer ?? true,
    }),
  });
  if (!res.ok) throw new Error('Query failed');
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
  if (!res.ok) throw new Error('Failed to fetch canonical');
  return res.json();
}

/** Fetch PDF file for a document (for viewer / Show on document). Returns blob URL; caller must revoke when done. */
export async function getDocumentFile(docId: string): Promise<string> {
  const res = await fetch(`${API_BASE}/documents/${encodeURIComponent(docId)}/file`, {
    headers: await authHeaders(),
  });
  if (!res.ok) throw new Error('Failed to fetch document file');
  const blob = await res.blob();
  return URL.createObjectURL(blob);
}
