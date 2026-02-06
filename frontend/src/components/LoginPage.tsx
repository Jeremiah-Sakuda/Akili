import React, { useState } from 'react';
import { useAuth } from '../contexts/AuthContext';

/**
 * Login page matching UI-SPEC: engineering tone, accent #0066CC,
 * typography (page title 1.5rem/600, body 0.875rem), 40px button height.
 */
const LoginPage: React.FC = () => {
  const { signInWithGoogle, authAvailable } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const [signingIn, setSigningIn] = useState(false);

  const handleGoogleSignIn = async () => {
    setError(null);
    setSigningIn(true);
    try {
      await signInWithGoogle();
    } catch (e) {
      const message = e instanceof Error ? e.message : 'Sign-in failed. Please try again.';
      setError(message);
    } finally {
      setSigningIn(false);
    }
  };

  if (!authAvailable) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center px-4 bg-white dark:bg-gray-900 text-gray-800 dark:text-slate-100 font-sans">
        <div className="max-w-md w-full border border-gray-200 dark:border-gray-600 p-6 text-center rounded-lg bg-white dark:bg-gray-800 shadow-sm">
          <h1 className="font-semibold mb-2 text-2xl">Akili</h1>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Firebase is not configured. Set VITE_FIREBASE_* in .env to enable sign-in.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-4 bg-slate-50 dark:bg-gray-900 text-slate-900 dark:text-slate-100 font-sans">
      <div className="max-w-sm w-full border border-slate-200 dark:border-gray-600 p-8 flex flex-col items-center rounded-lg bg-white dark:bg-gray-800 shadow-sm">
        {/* Logo + title — matches Header branding */}
        <div className="flex items-center gap-3 mb-2">
          <div className="size-10 rounded-lg flex items-center justify-center text-white bg-primary">
            <svg fill="none" height="22" viewBox="0 0 24 24" width="22" xmlns="http://www.w3.org/2000/svg">
              <path
                d="M12 2L2 7L12 12L22 7L12 2Z"
                stroke="currentColor"
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2"
              />
              <path
                d="M2 17L12 22L22 17"
                stroke="currentColor"
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2"
              />
              <path
                d="M2 12L12 17L22 12"
                stroke="currentColor"
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2"
              />
            </svg>
          </div>
          <h1 className="font-semibold tracking-tight text-2xl">Akili</h1>
        </div>
        <p className="text-center mb-6 text-sm text-slate-500 dark:text-slate-400">
          Verification workspace. Sign in to continue.
        </p>

        {error && (
          <div className="w-full mb-4 rounded-lg border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/20 px-3 py-2 text-sm text-red-700 dark:text-red-300">
            {error}
          </div>
        )}

        <button
          type="button"
          onClick={handleGoogleSignIn}
          disabled={signingIn}
          className="w-full h-10 flex items-center justify-center gap-3 rounded-lg border border-slate-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-slate-800 dark:text-slate-200 text-sm font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:ring-offset-white dark:focus:ring-offset-gray-800 disabled:opacity-60 hover:bg-slate-50 dark:hover:bg-gray-600"
        >
          {signingIn ? (
            <span className="text-slate-500 dark:text-slate-400">Signing in…</span>
          ) : (
            <>
              <svg width="20" height="20" viewBox="0 0 24 24" className="shrink-0">
                <path
                  fill="#4285F4"
                  d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                />
                <path
                  fill="#34A853"
                  d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                />
                <path
                  fill="#FBBC05"
                  d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                />
                <path
                  fill="#EA4335"
                  d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                />
              </svg>
              Sign in with Google
            </>
          )}
        </button>
      </div>
    </div>
  );
};

export default LoginPage;
