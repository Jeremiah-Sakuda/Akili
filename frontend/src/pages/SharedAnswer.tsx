import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';

interface SharedAnswerData {
  question_id: string;
  question: string;
  answer: string;
  status: 'VERIFIED' | 'REVIEW' | 'REFUSED';
  confidence: number | null;
  proof_data: {
    page?: number;
    coordinates?: { x: number; y: number };
    source_id?: string;
    rule?: string;
  } | null;
  source_page: number | null;
  created_at: string | null;
}

/**
 * Public page for viewing shared answers (FR-SHARE-2).
 * Displays the verified answer with proof information.
 * No authentication required.
 */
const SharedAnswer: React.FC = () => {
  const { questionId } = useParams<{ questionId: string }>();
  const [data, setData] = useState<SharedAnswerData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchAnswer = async () => {
      if (!questionId) {
        setError('Invalid question ID');
        setLoading(false);
        return;
      }

      try {
        const response = await fetch(`/api/q/${questionId}`);
        if (!response.ok) {
          if (response.status === 404) {
            setError('This shared answer was not found or has been removed.');
          } else {
            setError('Failed to load the shared answer.');
          }
          setLoading(false);
          return;
        }

        const result = await response.json();
        setData(result);
      } catch {
        setError('Failed to load the shared answer.');
      } finally {
        setLoading(false);
      }
    };

    fetchAnswer();
  }, [questionId]);

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0a0f1c] text-[#f0f2f5] flex items-center justify-center">
        <div className="flex items-center gap-3">
          <div className="w-6 h-6 border-2 border-[#0066CC] border-t-transparent rounded-full animate-spin" />
          <span className="text-[#8b95a8]">Loading...</span>
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="min-h-screen bg-[#0a0f1c] text-[#f0f2f5] flex flex-col items-center justify-center px-6">
        <div className="text-center max-w-md">
          <span className="material-symbols-outlined text-[64px] text-[#D44040] mb-4">error</span>
          <h1 className="text-2xl font-bold mb-2">Answer Not Found</h1>
          <p className="text-[#8b95a8] mb-8">{error}</p>
          <Link
            to="/"
            className="px-6 py-3 bg-[#0066CC] text-white font-semibold rounded-md hover:shadow-[0_0_24px_rgba(0,102,204,0.35)] transition-all"
          >
            Try AKILI Yourself
          </Link>
        </div>
      </div>
    );
  }

  const statusColors = {
    VERIFIED: { bg: 'bg-[#2DA66A]/10', text: 'text-[#2DA66A]', icon: 'verified' },
    REVIEW: { bg: 'bg-[#D4A017]/10', text: 'text-[#D4A017]', icon: 'rate_review' },
    REFUSED: { bg: 'bg-[#D44040]/10', text: 'text-[#D44040]', icon: 'block' },
  };

  const statusStyle = statusColors[data.status] || statusColors.REVIEW;

  return (
    <div className="min-h-screen bg-[#0a0f1c] text-[#f0f2f5]">
      {/* Header */}
      <header className="px-6 py-4 border-b border-white/6">
        <div className="max-w-3xl mx-auto flex items-center justify-between">
          <Link to="/" className="flex items-center gap-3">
            <div className="w-8 h-8 bg-[#0066CC] rounded-md flex items-center justify-center">
              <svg fill="none" height="18" viewBox="0 0 24 24" width="18" xmlns="http://www.w3.org/2000/svg">
                <path d="M12 2L2 7L12 12L22 7L12 2Z" stroke="white" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" />
                <path d="M2 17L12 22L22 17" stroke="white" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" />
                <path d="M2 12L12 17L22 12" stroke="white" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" />
              </svg>
            </div>
            <span className="font-bold text-xl tracking-tight">Akili</span>
          </Link>
          <Link
            to="/"
            className="px-4 py-2 bg-[#0066CC] text-white text-sm font-semibold rounded-md hover:shadow-[0_0_20px_rgba(0,102,204,0.35)] transition-all"
          >
            Try AKILI
          </Link>
        </div>
      </header>

      {/* Content */}
      <main className="px-6 py-12">
        <div className="max-w-3xl mx-auto">
          {/* Shared badge */}
          <div className="flex items-center gap-2 mb-6">
            <span className="material-symbols-outlined text-[16px] text-[#8b95a8]">share</span>
            <span className="text-sm text-[#8b95a8]">Shared Answer</span>
            {data.created_at && (
              <>
                <span className="text-[#8b95a8]">•</span>
                <span className="text-sm text-[#8b95a8]">
                  {new Date(data.created_at).toLocaleDateString()}
                </span>
              </>
            )}
          </div>

          {/* Question */}
          <div className="mb-8">
            <h1 className="text-2xl sm:text-3xl font-bold mb-2">{data.question}</h1>
          </div>

          {/* Answer card */}
          <div className="border border-white/10 rounded-lg bg-[#161d2e] overflow-hidden">
            {/* Status header */}
            <div className={`px-6 py-4 border-b border-white/6 ${statusStyle.bg} flex items-center gap-3`}>
              <span className={`material-symbols-outlined text-[20px] ${statusStyle.text}`}>
                {statusStyle.icon}
              </span>
              <span className={`font-bold text-sm tracking-wide uppercase ${statusStyle.text}`}>
                {data.status}
              </span>
              {data.confidence && (
                <span className="ml-auto font-mono text-sm text-[#8b95a8]">
                  {Math.round(data.confidence * 100)}% confidence
                </span>
              )}
            </div>

            {/* Answer */}
            <div className="px-6 py-6">
              <p className="text-xl font-semibold mb-6">{data.answer}</p>

              {/* Proof data */}
              {data.proof_data && (
                <div className="space-y-3 border-t border-white/6 pt-4">
                  <p className="text-xs font-mono text-[#8b95a8] uppercase tracking-wider mb-2">
                    Proof Details
                  </p>
                  {data.proof_data.source_id && (
                    <div className="flex items-center gap-2 text-sm text-[#8b95a8]">
                      <span className="material-symbols-outlined text-[14px] text-[#0066CC]">database</span>
                      <span className="font-mono">Source: {data.proof_data.source_id}</span>
                    </div>
                  )}
                  {data.proof_data.rule && (
                    <div className="flex items-center gap-2 text-sm text-[#8b95a8]">
                      <span className="material-symbols-outlined text-[14px] text-[#0066CC]">rule</span>
                      <span className="font-mono">Rule: {data.proof_data.rule}</span>
                    </div>
                  )}
                  {(data.source_page || data.proof_data.page) && (
                    <div className="flex items-center gap-2 text-sm text-[#8b95a8]">
                      <span className="material-symbols-outlined text-[14px] text-[#0066CC]">description</span>
                      <span className="font-mono">Page: {data.source_page || data.proof_data.page}</span>
                    </div>
                  )}
                  {data.proof_data.coordinates && (
                    <div className="flex items-center gap-2 text-sm text-[#8b95a8]">
                      <span className="material-symbols-outlined text-[14px] text-[#0066CC]">pin_drop</span>
                      <span className="font-mono">
                        Coordinates: ({data.proof_data.coordinates.x.toFixed(2)}, {data.proof_data.coordinates.y.toFixed(2)})
                      </span>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* CTA */}
          <div className="mt-12 text-center">
            <p className="text-[#8b95a8] mb-4">
              Want to verify facts from your own datasheets?
            </p>
            <Link
              to="/"
              className="inline-block px-8 py-3 bg-[#0066CC] text-white font-semibold rounded-md hover:shadow-[0_0_24px_rgba(0,102,204,0.35)] transition-all hover:-translate-y-0.5"
            >
              Try AKILI Free
            </Link>
          </div>

          {/* Info */}
          <div className="mt-16 border-t border-white/6 pt-8">
            <div className="text-center">
              <p className="text-sm text-[#8b95a8] mb-2">
                AKILI is the reasoning control plane for mission-critical engineering.
              </p>
              <p className="text-xs text-[#8b95a8]/60">
                Every answer is tied to exact coordinates on source documents — or the system refuses.
              </p>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
};

export default SharedAnswer;
