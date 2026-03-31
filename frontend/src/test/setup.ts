import '@testing-library/jest-dom';
import { vi } from 'vitest';

// Mock firebase module globally — components import from firebase/auth
vi.mock('../firebase', () => ({
  getFirebaseAuth: vi.fn(() => null),
  logEvent: vi.fn(),
}));

// Mock IntersectionObserver (used by useScrollReveal)
class MockIntersectionObserver {
  observe = vi.fn();
  unobserve = vi.fn();
  disconnect = vi.fn();
}
vi.stubGlobal('IntersectionObserver', MockIntersectionObserver);

// Mock matchMedia
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});
