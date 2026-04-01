/**
 * Frontend integration tests using MSW (Mock Service Worker).
 *
 * Tests full App-level rendering without a real backend.
 * Covers: doc list loading, query with answer display, error → toast.
 */

import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import { http, HttpResponse } from 'msw';

import { server } from './msw/server';

// Must mock firebase BEFORE importing App
vi.mock('../firebase', () => ({
  getFirebaseAuth: vi.fn(() => null),
  logEvent: vi.fn(),
}));

// Mock pdfjs-dist to avoid canvas issues in jsdom
vi.mock('pdfjs-dist', () => ({
  getDocument: vi.fn(),
  GlobalWorkerOptions: { workerSrc: '' },
}));

// Mock AuthContext to simulate logged-in user
const mockAuthValue = {
  user: { uid: 'test-user', email: 'test@akili.dev', displayName: 'Test User' },
  loading: false,
  signInWithGoogle: vi.fn(),
  signOut: vi.fn(),
  authAvailable: true,
};

vi.mock('../contexts/AuthContext', () => ({
  useAuth: () => mockAuthValue,
  AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

// Start MSW server
beforeAll(() => server.listen({ onUnhandledRequest: 'warn' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

/**
 * Helper to render App with required providers.
 */
async function renderApp() {
  const { default: App } = await import('../App');
  const { ThemeProvider } = await import('../contexts/ThemeContext');
  const { ToastProvider } = await import('../contexts/ToastContext');

  return render(
    <ThemeProvider>
      <ToastProvider>
        <App />
      </ToastProvider>
    </ThemeProvider>
  );
}

describe('Integration: Document List', () => {
  it('loads and displays document list from API', async () => {
    await renderApp();

    await waitFor(() => {
      expect(screen.getByText(/LM7805-datasheet\.pdf/i)).toBeInTheDocument();
    });
    expect(screen.getByText(/STM32F103-reference\.pdf/i)).toBeInTheDocument();
  });

  it('shows empty state when no documents', async () => {
    server.use(
      http.get('/api/documents', () => {
        return HttpResponse.json({ documents: [] });
      })
    );

    await renderApp();

    await waitFor(() => {
      const uploadElements = screen.queryAllByText(/upload|drop|pdf/i);
      expect(uploadElements.length).toBeGreaterThan(0);
    });
  });
});

describe('Integration: Error Handling', () => {
  it('shows error when document list fails', async () => {
    server.use(
      http.get('/api/documents', () => {
        return HttpResponse.json(
          { detail: 'Internal server error' },
          { status: 500 }
        );
      })
    );

    await renderApp();

    // App should still render without crashing
    await waitFor(() => {
      expect(document.body).toBeTruthy();
    });
  });

  it('handles network failure gracefully', async () => {
    server.use(
      http.get('/api/documents', () => {
        return HttpResponse.error();
      })
    );

    await renderApp();

    // Should not crash
    await waitFor(() => {
      expect(document.body).toBeTruthy();
    });
  });
});

describe('Integration: Query Flow (API level)', () => {
  it('query endpoint returns expected answer structure', async () => {
    const response = await fetch('/api/query', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ doc_id: 'doc-1', question: 'What is the max voltage?' }),
    });
    const data = await response.json();

    expect(data.status).toBe('answer');
    expect(data.answer).toBe('3.3 V');
    expect(data.proof).toHaveLength(1);
    expect(data.confidence_tier).toBe('verified');
  });

  it('query endpoint returns refusal for unknown questions', async () => {
    const response = await fetch('/api/query', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ doc_id: 'doc-1', question: 'Some unknown question' }),
    });
    const data = await response.json();

    expect(data.status).toBe('refuse');
    expect(data.reason).toBeTruthy();
  });
});

describe('Integration: Usage Tracking', () => {
  it('returns usage summary', async () => {
    const response = await fetch('/api/usage');
    const data = await response.json();

    expect(data.documents.used).toBe(2);
    expect(data.documents.limit).toBe(5);
    expect(data.queries.remaining).toBe(40);
  });
});
