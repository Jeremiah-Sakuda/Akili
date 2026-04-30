import React from 'react';

interface UsageLimitModalProps {
  isOpen: boolean;
  onClose: () => void;
  limitType: 'documents' | 'queries';
  currentUsage: number;
  limit: number;
}

/**
 * Modal shown when user hits free tier limits (FR-CAP-3).
 * Displays friendly message and contact info.
 */
export const UsageLimitModal: React.FC<UsageLimitModalProps> = ({
  isOpen,
  onClose,
  limitType,
  currentUsage,
  limit,
}) => {
  if (!isOpen) return null;

  const limitMessages = {
    documents: {
      title: 'Document Limit Reached',
      description: "You've uploaded the maximum number of documents for the free tier this month.",
      detail: `${currentUsage} of ${limit} documents used`,
    },
    queries: {
      title: 'Query Limit Reached',
      description: "You've used all your free queries for this month.",
      detail: `${currentUsage} of ${limit} queries used`,
    },
  };

  const message = limitMessages[limitType];

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/50 z-50"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Modal */}
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="usage-limit-title"
        className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-50 w-full max-w-md"
      >
        <div className="bg-[#161d2e] border border-white/10 rounded-lg shadow-xl overflow-hidden">
          {/* Header */}
          <div className="px-6 py-4 border-b border-white/6 bg-[#D4A017]/10">
            <div className="flex items-center gap-3">
              <span className="material-symbols-outlined text-[24px] text-[#D4A017]">
                hourglass_empty
              </span>
              <h2 id="usage-limit-title" className="text-lg font-semibold text-white">
                {message.title}
              </h2>
            </div>
          </div>

          {/* Content */}
          <div className="px-6 py-5">
            <p className="text-[#f0f2f5] mb-3">
              {message.description}
            </p>
            <p className="text-sm text-[#8b95a8] mb-4">
              {message.detail}
            </p>

            <div className="bg-white/5 rounded-lg p-4 mb-4">
              <p className="text-sm text-[#f0f2f5] mb-2">
                Want more?
              </p>
              <p className="text-sm text-[#8b95a8]">
                Email{' '}
                <a
                  href="mailto:jeremiah@akili.app?subject=AKILI%20Usage%20Limit"
                  className="text-[#0066CC] hover:underline"
                >
                  jeremiah@akili.app
                </a>
                {' '}to discuss your needs.
              </p>
            </div>

            <p className="text-xs text-[#8b95a8]">
              Usage resets at the start of each month.
            </p>
          </div>

          {/* Footer */}
          <div className="px-6 py-4 border-t border-white/6 flex justify-end">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 bg-[#0066CC] text-white text-sm font-semibold rounded-md hover:shadow-[0_0_20px_rgba(0,102,204,0.35)] transition-all"
            >
              Got it
            </button>
          </div>
        </div>
      </div>
    </>
  );
};

export default UsageLimitModal;
