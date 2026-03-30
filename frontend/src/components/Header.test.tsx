import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import Header from './Header';

// Mock auth and theme contexts
const mockSignOut = vi.fn();
vi.mock('../contexts/AuthContext', () => ({
  useAuth: () => ({
    user: { email: 'engineer@example.com', photoURL: null },
    loading: false,
    signOut: mockSignOut,
    signInWithGoogle: vi.fn(),
    authAvailable: true,
  }),
}));

const mockSetTheme = vi.fn();
vi.mock('../contexts/ThemeContext', () => ({
  useTheme: () => ({
    theme: 'dark' as const,
    setTheme: mockSetTheme,
    themes: ['light', 'dark', 'very-dark'] as const,
  }),
}));

describe('Header', () => {
  it('renders Akili branding', () => {
    render(<Header />);
    expect(screen.getByText('Akili')).toBeInTheDocument();
    expect(screen.getByText('Verification')).toBeInTheDocument();
  });

  it('shows user initial when no photoURL', () => {
    render(<Header />);
    expect(screen.getByText('E')).toBeInTheDocument();
  });

  it('opens user menu and shows email on click', async () => {
    const user = userEvent.setup();
    render(<Header />);

    // Click user avatar button (contains the initial "E")
    const avatarButton = screen.getByText('E').closest('button')!;
    await user.click(avatarButton);

    expect(screen.getByText('engineer@example.com')).toBeInTheDocument();
    expect(screen.getByText('Sign out')).toBeInTheDocument();
  });

  it('calls signOut when sign out is clicked', async () => {
    const user = userEvent.setup();
    render(<Header />);

    const avatarButton = screen.getByText('E').closest('button')!;
    await user.click(avatarButton);
    await user.click(screen.getByText('Sign out'));

    expect(mockSignOut).toHaveBeenCalled();
  });
});
