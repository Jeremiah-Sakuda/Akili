import { useCallback, useRef, useEffect } from 'react';

// Google Analytics gtag type declaration
declare global {
  interface Window {
    gtag?: (command: string, action: string, params?: Record<string, unknown>) => void;
  }
}

const STORAGE_KEY_FIRST_VISIT = 'akili-first-visit-ts';
const STORAGE_KEY_FIRST_ANSWER = 'akili-first-answer-ts';
const STORAGE_KEY_FIRST_QUERY_USED = 'akili-first-query-used';

/**
 * Hook for tracking onboarding metrics (FR-ON-3, FR-ON-4).
 * Tracks time-to-first-answer and first query usage.
 *
 * Target: < 90 seconds for cold path, < 5 seconds for corpus path.
 */
export function useOnboardingMetrics() {
  const sessionStart = useRef<number>(Date.now());

  // Record first visit timestamp
  useEffect(() => {
    if (typeof window === 'undefined') return;

    const existing = localStorage.getItem(STORAGE_KEY_FIRST_VISIT);
    if (!existing) {
      localStorage.setItem(STORAGE_KEY_FIRST_VISIT, Date.now().toString());
    }
  }, []);

  /**
   * Track time to first answer after page load.
   * Should be < 90 seconds for cold path.
   */
  const trackTimeToFirstAnswer = useCallback((startTime?: number) => {
    const elapsed = Date.now() - (startTime || sessionStart.current);
    const elapsedSeconds = Math.round(elapsed / 1000);

    // Log to analytics (placeholder - integrate with real analytics)
    console.log('[Onboarding] Time to first answer:', elapsedSeconds, 'seconds');

    // Store for analytics
    if (typeof window !== 'undefined') {
      const existing = localStorage.getItem(STORAGE_KEY_FIRST_ANSWER);
      if (!existing) {
        localStorage.setItem(STORAGE_KEY_FIRST_ANSWER, elapsed.toString());

        // Send to analytics if available
        if (typeof window.gtag === 'function') {
          window.gtag('event', 'time_to_first_answer', {
            value: elapsedSeconds,
            event_category: 'onboarding',
          });
        }
      }
    }

    return elapsedSeconds;
  }, []);

  /**
   * Check if user has used their first free query.
   * FR-ON-3: First query allowed without signup.
   */
  const checkFirstQueryUsed = useCallback((): boolean => {
    if (typeof window === 'undefined') return false;
    return localStorage.getItem(STORAGE_KEY_FIRST_QUERY_USED) === '1';
  }, []);

  /**
   * Mark first query as used.
   * After this, prompt for Google sign-in (FR-ON-4).
   */
  const markFirstQueryUsed = useCallback(() => {
    if (typeof window === 'undefined') return;
    localStorage.setItem(STORAGE_KEY_FIRST_QUERY_USED, '1');

    // Log to analytics
    console.log('[Onboarding] First free query used');

    if (typeof window.gtag === 'function') {
      window.gtag('event', 'first_query_used', {
        event_category: 'onboarding',
      });
    }
  }, []);

  /**
   * Track query path type for analytics.
   * @param pathType 'cold' for new document, 'corpus' for pre-cached
   */
  const trackQueryPath = useCallback((pathType: 'cold' | 'corpus', durationMs: number) => {
    const durationSeconds = Math.round(durationMs / 1000);

    console.log('[Onboarding] Query path:', pathType, 'Duration:', durationSeconds, 'seconds');

    if (typeof window.gtag === 'function') {
      window.gtag('event', 'query_path', {
        path_type: pathType,
        duration_seconds: durationSeconds,
        event_category: 'performance',
      });
    }
  }, []);

  /**
   * Get onboarding stats for debugging/display.
   */
  const getOnboardingStats = useCallback(() => {
    if (typeof window === 'undefined') {
      return { firstVisit: null, firstAnswer: null, firstQueryUsed: false };
    }

    const firstVisit = localStorage.getItem(STORAGE_KEY_FIRST_VISIT);
    const firstAnswer = localStorage.getItem(STORAGE_KEY_FIRST_ANSWER);
    const firstQueryUsed = localStorage.getItem(STORAGE_KEY_FIRST_QUERY_USED) === '1';

    return {
      firstVisit: firstVisit ? new Date(parseInt(firstVisit, 10)) : null,
      firstAnswer: firstAnswer ? parseInt(firstAnswer, 10) : null,
      firstQueryUsed,
    };
  }, []);

  /**
   * Reset all onboarding metrics (for testing).
   */
  const resetMetrics = useCallback(() => {
    if (typeof window === 'undefined') return;
    localStorage.removeItem(STORAGE_KEY_FIRST_VISIT);
    localStorage.removeItem(STORAGE_KEY_FIRST_ANSWER);
    localStorage.removeItem(STORAGE_KEY_FIRST_QUERY_USED);
    sessionStart.current = Date.now();
  }, []);

  return {
    trackTimeToFirstAnswer,
    checkFirstQueryUsed,
    markFirstQueryUsed,
    trackQueryPath,
    getOnboardingStats,
    resetMetrics,
  };
}

export default useOnboardingMetrics;
