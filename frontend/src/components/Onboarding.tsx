import React from 'react';
import type { OnboardingStep } from '../hooks/useOnboarding';

interface OnboardingProps {
  step: OnboardingStep;
  onNext: () => void;
  onSkip: () => void;
}

const STEP_CONTENT: Record<Exclude<OnboardingStep, 'done'>, { icon: string; title: string; description: string; cta: string }> = {
  welcome: {
    icon: 'layers',
    title: 'Welcome to Akili',
    description: 'The verification engine for mission-critical engineering documents. Every answer is tied to exact coordinates — or the system refuses.',
    cta: 'Get Started',
  },
  upload: {
    icon: 'cloud_upload',
    title: 'Upload a Document',
    description: 'Start by uploading a technical PDF (datasheet, schematic, spec sheet). Akili will extract and canonicalize all facts with coordinate grounding.',
    cta: 'Next',
  },
  query: {
    icon: 'search',
    title: 'Ask a Question',
    description: 'Type a question in the verification chat. Akili will answer with proof locations or refuse if the fact cannot be verified.',
    cta: 'Start Verifying',
  },
};

const Onboarding: React.FC<OnboardingProps> = ({ step, onNext, onSkip }) => {
  if (step === 'done') return null;

  const content = STEP_CONTENT[step];
  const stepNum = step === 'welcome' ? 1 : step === 'upload' ? 2 : 3;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="bg-white dark:bg-[#161b22] border border-gray-200 dark:border-[#30363d] rounded-xl shadow-2xl max-w-md w-full mx-4 p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex gap-1.5">
            {[1, 2, 3].map((n) => (
              <div
                key={n}
                className={`w-8 h-1 rounded-full transition-colors ${
                  n <= stepNum ? 'bg-primary' : 'bg-gray-200 dark:bg-[#30363d]'
                }`}
              />
            ))}
          </div>
          <button
            type="button"
            onClick={onSkip}
            className="text-xs text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 transition-colors"
          >
            Skip
          </button>
        </div>

        <div className="flex flex-col items-center text-center py-4">
          <div className="w-14 h-14 bg-primary/10 dark:bg-primary/20 rounded-xl flex items-center justify-center mb-4">
            <span className="material-symbols-outlined text-[28px] text-primary">{content.icon}</span>
          </div>
          <h2 className="text-lg font-heading text-gray-900 dark:text-gray-100 mb-2">{content.title}</h2>
          <p className="text-sm text-gray-600 dark:text-gray-400 leading-relaxed max-w-sm">{content.description}</p>
        </div>

        <button
          type="button"
          onClick={onNext}
          className="w-full mt-4 py-2.5 bg-primary text-white font-medium rounded-lg hover:bg-[#0052a3] transition-colors"
        >
          {content.cta}
        </button>
      </div>
    </div>
  );
};

export default Onboarding;
