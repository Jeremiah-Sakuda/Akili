/**
 * API client for Akili FastAPI backend.
 * In dev, Vite proxy forwards /api/* to the backend (see vite.config.ts).
 */

const API_BASE = '/api';

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
}

export interface ProofPoint {
  x: number;
  y: number;
  source_id?: string | null;
  source_type?: string | null;
}

export interface AnswerWithProof {
  status: 'answer';
  answer: string;
  proof: ProofPoint[];
  source_id?: string | null;
  source_type?: string | null;
}

export interface Refuse {
  status: 'refuse';
  reason: string;
}

export type QueryResponse = AnswerWithProof | Refuse;

export async function getDocuments(): Promise<DocumentSummary[]> {
  const res = await fetch(`${API_BASE}/documents`);
  if (!res.ok) throw new Error('Failed to fetch documents');
  const data = await res.json();
  return data.documents ?? [];
}

export async function ingest(file: File): Promise<IngestResponse> {
  const form = new FormData();
  form.append('file', file);
  const res = await fetch(`${API_BASE}/ingest`, {
    method: 'POST',
    body: form,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? 'Ingest failed');
  }
  return res.json();
}

export async function query(docId: string, question: string): Promise<QueryResponse> {
  const res = await fetch(`${API_BASE}/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ doc_id: docId, question }),
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
