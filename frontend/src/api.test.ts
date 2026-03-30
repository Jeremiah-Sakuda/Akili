import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock firebase before importing api module
vi.mock('./firebase', () => ({
  getFirebaseAuth: vi.fn(() => null),
}));

// Must import after mocks are set up
const { getDocuments, query, isRefuse, isAnswer, deleteDocument } = await import('./api');

describe('api client', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('getDocuments returns document list on success', async () => {
    const mockDocs = [{ doc_id: 'abc', filename: 'test.pdf', page_count: 3, created_at: '', units_count: 5, bijections_count: 2, grids_count: 1 }];
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ documents: mockDocs }),
    } as Response);

    const docs = await getDocuments();
    expect(docs).toEqual(mockDocs);
    expect(docs[0].doc_id).toBe('abc');
  });

  it('getDocuments throws on non-ok response', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: false,
      status: 500,
    } as Response);

    await expect(getDocuments()).rejects.toThrow('Failed to fetch documents');
  });

  it('query sends correct request body', async () => {
    const mockResult = { status: 'answer', answer: '3.3V', proof: [] };
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: () => Promise.resolve(mockResult),
    } as Response);

    const result = await query('doc123', 'What is the max voltage?');
    expect(result).toEqual(mockResult);

    const [url, options] = fetchSpy.mock.calls[0];
    expect(url).toContain('/query');
    const body = JSON.parse(options!.body as string);
    expect(body.doc_id).toBe('doc123');
    expect(body.question).toBe('What is the max voltage?');
  });

  it('isRefuse correctly identifies refuse responses', () => {
    expect(isRefuse({ status: 'refuse', reason: 'No data' })).toBe(true);
    expect(isRefuse({ status: 'answer', answer: '3.3V', proof: [] })).toBe(false);
  });

  it('isAnswer correctly identifies answer responses', () => {
    expect(isAnswer({ status: 'answer', answer: '3.3V', proof: [] })).toBe(true);
    expect(isAnswer({ status: 'refuse', reason: 'No data' })).toBe(false);
  });

  it('deleteDocument calls DELETE endpoint', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ doc_id: 'abc', deleted: true }),
    } as Response);

    await deleteDocument('abc');

    const [url, options] = fetchSpy.mock.calls[0];
    expect(url).toContain('/documents/abc');
    expect(options!.method).toBe('DELETE');
  });
});
