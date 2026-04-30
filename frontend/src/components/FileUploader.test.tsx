import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import FileUploader from './FileUploader';

vi.mock('../api', () => ({
  ingestStream: vi.fn(),
  getUsage: vi.fn(() => Promise.resolve({ documents: { used: 1, limit: 5, remaining: 4 }, queries: { used: 3, limit: 50, remaining: 47 } })),
}));

describe('FileUploader', () => {
  it('renders upload prompt in idle state', () => {
    render(<FileUploader onSuccess={vi.fn()} />);
    expect(screen.getByText('Upload Technical Document')).toBeInTheDocument();
    expect(screen.getByText(/Drag & drop PDFs here/)).toBeInTheDocument();
    expect(screen.getByText('SUPPORTED: PDF (single or multiple)')).toBeInTheDocument();
  });

  it('shows error for non-PDF file via drag-and-drop', () => {
    render(<FileUploader onSuccess={vi.fn()} />);

    const dropZone = screen.getByText('Upload Technical Document').closest('.file-uploader-root')!;
    const file = new File(['hello'], 'test.txt', { type: 'text/plain' });
    fireEvent.drop(dropZone, { dataTransfer: { files: [file] } });

    expect(screen.getByText(/is not a PDF/)).toBeInTheDocument();
  });

  it('renders back button when onBack is provided', async () => {
    const onBack = vi.fn();
    const user = userEvent.setup();
    render(<FileUploader onSuccess={vi.fn()} onBack={onBack} />);

    const backBtn = screen.getByText('Back');
    expect(backBtn).toBeInTheDocument();
    await user.click(backBtn);
    expect(onBack).toHaveBeenCalled();
  });

  it('shows system status cards', () => {
    render(<FileUploader onSuccess={vi.fn()} />);
    expect(screen.getByText('Ready for Ingest')).toBeInTheDocument();
    expect(screen.getByText('Akili Backend')).toBeInTheDocument();
  });
});
