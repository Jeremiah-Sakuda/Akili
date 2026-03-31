import { useCallback, useState } from 'react';

const STORAGE_KEY = 'akili-onboarding-complete';

export type OnboardingStep = 'welcome' | 'upload' | 'query' | 'done';

const STEPS: OnboardingStep[] = ['welcome', 'upload', 'query', 'done'];

export function useOnboarding() {
  const [step, setStep] = useState<OnboardingStep>(() => {
    if (typeof window === 'undefined') return 'done';
    return localStorage.getItem(STORAGE_KEY) === '1' ? 'done' : 'welcome';
  });

  const next = useCallback(() => {
    setStep((prev) => {
      const idx = STEPS.indexOf(prev);
      const nextStep = STEPS[Math.min(idx + 1, STEPS.length - 1)];
      if (nextStep === 'done') {
        localStorage.setItem(STORAGE_KEY, '1');
      }
      return nextStep;
    });
  }, []);

  const skip = useCallback(() => {
    localStorage.setItem(STORAGE_KEY, '1');
    setStep('done');
  }, []);

  const reset = useCallback(() => {
    localStorage.removeItem(STORAGE_KEY);
    setStep('welcome');
  }, []);

  return { step, next, skip, reset, isComplete: step === 'done' };
}
