/**
 * MSW request handlers for integration tests.
 * Simulates the Akili backend API responses.
 */

import { http, HttpResponse } from 'msw';

const API_BASE = '/api';

export const mockDocuments = [
  {
    doc_id: 'doc-1',
    filename: 'LM7805-datasheet.pdf',
    page_count: 12,
    created_at: '2026-03-15T10:30:00',
    units_count: 45,
    bijections_count: 3,
    grids_count: 8,
  },
  {
    doc_id: 'doc-2',
    filename: 'STM32F103-reference.pdf',
    page_count: 80,
    created_at: '2026-03-16T14:00:00',
    units_count: 120,
    bijections_count: 10,
    grids_count: 25,
  },
];

export const mockQueryAnswer = {
  status: 'answer',
  answer: '3.3 V',
  proof: [
    { x: 0.45, y: 0.32, page: 2, source_id: 'u_vcc', source_type: 'unit' },
  ],
  source_id: 'u_vcc',
  source_type: 'unit',
  confidence: {
    extraction_agreement: 0.85,
    canonical_validation: 0.9,
    verification_strength: 0.8,
    overall: 0.85,
  },
  confidence_tier: 'verified',
  formatting_source: 'verified_raw',
};

export const mockQueryRefusal = {
  status: 'refuse',
  reason: 'No canonical fact derives this answer.',
  formatting_source: 'verified_raw',
};

export const mockUsage = {
  documents: { used: 2, limit: 5, remaining: 3 },
  queries: { used: 10, limit: 50, remaining: 40 },
};

export const handlers = [
  // Document list
  http.get(`${API_BASE}/documents`, () => {
    return HttpResponse.json({ documents: mockDocuments });
  }),

  // Delete document
  http.delete(`${API_BASE}/documents/:docId`, ({ params }) => {
    return HttpResponse.json({ doc_id: params.docId, deleted: true });
  }),

  // Query endpoint
  http.post(`${API_BASE}/query`, async ({ request }) => {
    const body = (await request.json()) as { question: string };
    // Simulate a refusal for unknown questions
    if (body.question?.toLowerCase().includes('unknown')) {
      return HttpResponse.json(mockQueryRefusal);
    }
    return HttpResponse.json(mockQueryAnswer);
  }),

  // Usage
  http.get(`${API_BASE}/usage`, () => {
    return HttpResponse.json(mockUsage);
  }),

  // Health
  http.get(`${API_BASE}/health`, () => {
    return HttpResponse.json({ status: 'ok' });
  }),

  // Ingest (non-streaming)
  http.post(`${API_BASE}/ingest`, () => {
    return HttpResponse.json({
      doc_id: 'doc-new',
      filename: 'test-upload.pdf',
      page_count: 5,
      units_count: 20,
      bijections_count: 2,
      grids_count: 4,
      pages_failed: 0,
    });
  }),
];
