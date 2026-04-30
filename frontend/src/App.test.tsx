import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import App from './App';

interface MockSidebarProps {
  files?: { id: string }[];
}

interface MockQueryResponse {
  status: string;
}

interface MockAuthValue {
  user: { email: string } | null;
  loading: boolean;
  signInWithGoogle: ReturnType<typeof vi.fn>;
  signOut: ReturnType<typeof vi.fn>;
  authAvailable: boolean;
}

// Mock all child components to isolate App logic
vi.mock('./components/Header', () => ({ default: () => <div data-testid="header">Header</div> }));
vi.mock('./components/SidebarLeft', () => ({ default: (props: MockSidebarProps) => <div data-testid="sidebar-left">{props.files?.length ?? 0} docs</div> }));
vi.mock('./components/SidebarRight', () => ({ default: () => <div data-testid="sidebar-right">SidebarRight</div> }));
vi.mock('./components/DocumentViewer', () => ({ default: () => <div data-testid="doc-viewer">DocViewer</div> }));
vi.mock('./components/FileUploader', () => ({ default: () => <div data-testid="file-uploader">FileUploader</div> }));
vi.mock('./components/LandingPage', () => ({ default: () => <div data-testid="landing-page">LandingPage</div> }));
vi.mock('./components/Toast', () => ({ default: () => null }));

const mockGetDocuments = vi.fn(() => Promise.resolve([]));
vi.mock('./api', () => ({
  getDocuments: () => mockGetDocuments(),
  deleteDocument: vi.fn(),
  query: vi.fn(),
  isRefuse: (r: MockQueryResponse) => r.status === 'refuse',
}));

let mockAuthValue: MockAuthValue = { user: null, loading: false, signInWithGoogle: vi.fn(), signOut: vi.fn(), authAvailable: true };
vi.mock('./contexts/AuthContext', () => ({
  useAuth: () => mockAuthValue,
}));

vi.mock('./contexts/ToastContext', () => ({
  useToast: () => ({ toasts: [], addToast: vi.fn(), removeToast: vi.fn() }),
}));

describe('App', () => {
  beforeEach(() => {
    mockAuthValue = { user: null, loading: false, signInWithGoogle: vi.fn(), signOut: vi.fn(), authAvailable: true };
    mockGetDocuments.mockResolvedValue([]);
  });

  it('shows loading spinner when auth is loading', () => {
    mockAuthValue = { ...mockAuthValue, loading: true };
    render(<App />);
    expect(screen.getByText('Loading…')).toBeInTheDocument();
  });

  it('shows landing page when user is null', () => {
    render(<App />);
    expect(screen.getByTestId('landing-page')).toBeInTheDocument();
  });

  it('shows main layout when user is authenticated', async () => {
    mockAuthValue = { ...mockAuthValue, user: { email: 'test@test.com' } };
    render(<App />);
    expect(screen.getByTestId('header')).toBeInTheDocument();
    expect(screen.getByTestId('sidebar-left')).toBeInTheDocument();
    expect(screen.getByTestId('sidebar-right')).toBeInTheDocument();
  });

  it('shows FileUploader in initial UPLOAD state', () => {
    mockAuthValue = { ...mockAuthValue, user: { email: 'test@test.com' } };
    render(<App />);
    expect(screen.getByTestId('file-uploader')).toBeInTheDocument();
  });
});
