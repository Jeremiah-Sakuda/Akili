import React, { createContext, useCallback, useContext, useEffect, useState } from 'react';
import type { User } from 'firebase/auth';
import { getFirebaseAuth } from '../firebase';
import {
  GoogleAuthProvider,
  getRedirectResult,
  onAuthStateChanged,
  signInWithRedirect,
  signOut as firebaseSignOut,
} from 'firebase/auth';

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  signInWithGoogle: () => Promise<void>;
  signOut: () => Promise<void>;
  authAvailable: boolean;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const auth = getFirebaseAuth();
  const authAvailable = !!auth;

  useEffect(() => {
    if (!auth) {
      setLoading(false);
      return;
    }
    const unsubscribe = onAuthStateChanged(auth, (u) => {
      setUser(u);
      setLoading(false);
    });
    getRedirectResult(auth).catch(() => {});
    return () => unsubscribe();
  }, [auth]);

  const signInWithGoogle = useCallback(async () => {
    if (!auth) return;
    const provider = new GoogleAuthProvider();
    await signInWithRedirect(auth, provider);
  }, [auth]);

  const signOut = useCallback(async () => {
    if (!auth) return;
    await firebaseSignOut(auth);
  }, [auth]);

  const value: AuthContextValue = {
    user,
    loading,
    signInWithGoogle,
    signOut,
    authAvailable,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

/** Hook for consumers; file also exports AuthProvider so react-refresh warns. */
// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
