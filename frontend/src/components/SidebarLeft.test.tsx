import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import SidebarLeft from './SidebarLeft';
import { AppState } from '../types';
import type { DocumentFile } from '../types';

vi.mock('../api', () => ({
  getCanonical: vi.fn(() =>
    Promise.resolve({ doc_id: 'd1', units: [], bijections: [], grids: [] })
  ),
}));

vi.mock('../hooks/useReveal', () => ({
  useReveal: () => ({ ref: { current: null }, revealClass: 'reveal visible' }),
}));

const mockFiles: DocumentFile[] = [
  { id: 'doc1', name: 'datasheet.pdf', meta: '5 units · 2 bijections · 1 grids', icon: 'description', active: true },
  { id: 'doc2', name: 'schematic.pdf', meta: '3 units · 0 bijections · 0 grids', icon: 'description', active: false },
];

describe('SidebarLeft', () => {
  it('renders document list', () => {
    render(
      <SidebarLeft
        currentState={AppState.VERIFIED}
        onStateChange={vi.fn()}
        files={mockFiles}
        selectedDocId="doc1"
        onSelectFile={vi.fn()}
      />
    );
    expect(screen.getByText('datasheet.pdf')).toBeInTheDocument();
    expect(screen.getByText('schematic.pdf')).toBeInTheDocument();
  });

  it('shows skeleton rows when loading', () => {
    const { container } = render(
      <SidebarLeft
        currentState={AppState.VERIFIED}
        onStateChange={vi.fn()}
        files={[]}
        selectedDocId={null}
        loading={true}
        onSelectFile={vi.fn()}
      />
    );
    const skeletons = container.querySelectorAll('.skeleton');
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it('shows empty state when no documents', () => {
    render(
      <SidebarLeft
        currentState={AppState.VERIFIED}
        onStateChange={vi.fn()}
        files={[]}
        selectedDocId={null}
        loading={false}
        onSelectFile={vi.fn()}
      />
    );
    expect(screen.getByText('No documents yet.')).toBeInTheDocument();
    expect(screen.getByText('Upload a PDF to get started.')).toBeInTheDocument();
  });

  it('calls onSelectFile when document clicked', async () => {
    const user = userEvent.setup();
    const onSelectFile = vi.fn();
    render(
      <SidebarLeft
        currentState={AppState.VERIFIED}
        onStateChange={vi.fn()}
        files={mockFiles}
        selectedDocId="doc1"
        onSelectFile={onSelectFile}
      />
    );

    await user.click(screen.getByText('schematic.pdf'));
    expect(onSelectFile).toHaveBeenCalledWith('doc2');
  });

  it('shows API connected status', () => {
    render(
      <SidebarLeft
        currentState={AppState.VERIFIED}
        onStateChange={vi.fn()}
        files={mockFiles}
        selectedDocId="doc1"
        onSelectFile={vi.fn()}
      />
    );
    expect(screen.getByText('API connected')).toBeInTheDocument();
  });
});
