/* eslint-disable react-refresh/only-export-components -- entry point: no exports */
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import { AuthProvider } from './contexts/AuthContext';
import { ThemeProvider } from './contexts/ThemeContext';
import './index.css';

const rootElement = document.getElementById('root');
if (!rootElement) {
  throw new Error('Root element not found');
}

function ErrorFallback({ error }: { error: Error }) {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-6 bg-background-light dark:bg-gray-900 text-slate-800 dark:text-slate-200 font-sans">
      <div className="max-w-lg w-full rounded-lg border border-red-200 dark:border-red-800 bg-red-50/50 dark:bg-red-900/20 p-6">
        <h1 className="text-lg font-semibold text-red-800 dark:text-red-300 mb-2">Something went wrong</h1>
        <p className="text-sm text-red-700 dark:text-red-400 mb-3 font-mono break-all">{error.message}</p>
        <p className="text-xs text-slate-500 dark:text-slate-400">Check the browser console for details.</p>
      </div>
    </div>
  );
}

class ErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { error: Error | null }
> {
  state = { error: null as Error | null };
  static getDerivedStateFromError(error: Error) {
    return { error };
  }
  render() {
    if (this.state.error) return <ErrorFallback error={this.state.error} />;
    return this.props.children;
  }
}

function AppWithErrorBoundary() {
  const [runtimeError, setRuntimeError] = React.useState<Error | null>(null);
  React.useEffect(() => {
    const onError = (e: ErrorEvent) => setRuntimeError(e.error ?? new Error('Unknown error'));
    window.addEventListener('error', onError);
    return () => window.removeEventListener('error', onError);
  }, []);
  if (runtimeError) return <ErrorFallback error={runtimeError} />;
  return (
    <React.StrictMode>
      <ErrorBoundary>
        <ThemeProvider>
          <AuthProvider>
            <App />
          </AuthProvider>
        </ThemeProvider>
      </ErrorBoundary>
    </React.StrictMode>
  );
}

ReactDOM.createRoot(rootElement).render(<AppWithErrorBoundary />);
