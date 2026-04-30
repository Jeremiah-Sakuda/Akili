import React, { useState } from 'react';

interface ShareButtonProps {
  questionId: string;
  question: string;
  answer: string;
  status: 'VERIFIED' | 'REVIEW' | 'REFUSED';
  onShare?: (url: string) => void;
}

/**
 * Share button with social sharing options (FR-SHARE-3).
 * Allows copying permalink and sharing to social platforms.
 */
export const ShareButton: React.FC<ShareButtonProps> = ({
  questionId,
  question,
  answer,
  status,
  onShare,
}) => {
  const [showMenu, setShowMenu] = useState(false);
  const [copied, setCopied] = useState(false);

  const shareUrl = `https://akili.app/q/${questionId}`;
  const shareText = `${question}\n\nAnswer: ${answer} (${status})\n\nVerified with AKILI`;

  const copyLink = async () => {
    try {
      await navigator.clipboard.writeText(shareUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
      onShare?.(shareUrl);
    } catch (err) {
      console.error('Failed to copy link:', err);
    }
  };

  const shareToReddit = () => {
    const title = encodeURIComponent(`${question} - Verified answer from AKILI`);
    const url = encodeURIComponent(shareUrl);
    window.open(`https://reddit.com/submit?url=${url}&title=${title}`, '_blank');
    onShare?.(shareUrl);
  };

  const shareToX = () => {
    const text = encodeURIComponent(`${shareText}\n\n${shareUrl}`);
    window.open(`https://twitter.com/intent/tweet?text=${text}`, '_blank');
    onShare?.(shareUrl);
  };

  const shareToLinkedIn = () => {
    const url = encodeURIComponent(shareUrl);
    window.open(`https://www.linkedin.com/sharing/share-offsite/?url=${url}`, '_blank');
    onShare?.(shareUrl);
  };

  const shareToDiscord = () => {
    // Discord doesn't have a direct share URL, so we just copy
    copyLink();
  };

  // Only allow sharing VERIFIED answers
  if (status !== 'VERIFIED') {
    return null;
  }

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setShowMenu(!showMenu)}
        className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-[#8b95a8] hover:text-white border border-white/10 rounded hover:border-white/20 transition-colors"
        aria-label="Share this answer"
      >
        <span className="material-symbols-outlined text-[14px]">share</span>
        Share
      </button>

      {showMenu && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 z-40"
            onClick={() => setShowMenu(false)}
          />

          {/* Menu */}
          <div className="absolute right-0 mt-2 w-48 bg-[#1a2235] border border-white/10 rounded-lg shadow-xl z-50 overflow-hidden">
            <div className="p-2 border-b border-white/6">
              <p className="text-xs text-[#8b95a8] mb-1">Share verified answer</p>
            </div>

            <div className="p-1">
              <ShareMenuItem
                icon="content_copy"
                label={copied ? 'Copied!' : 'Copy link'}
                onClick={copyLink}
                highlight={copied}
              />
              <ShareMenuItem
                icon="reddit"
                label="Reddit"
                onClick={shareToReddit}
                iconClass="text-[#FF4500]"
              />
              <ShareMenuItem
                icon="close"
                label="X (Twitter)"
                onClick={shareToX}
                useCustomIcon
                customIcon={
                  <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
                  </svg>
                }
              />
              <ShareMenuItem
                icon="linkedin"
                label="LinkedIn"
                onClick={shareToLinkedIn}
                iconClass="text-[#0A66C2]"
              />
              <ShareMenuItem
                icon="discord"
                label="Discord"
                onClick={shareToDiscord}
                iconClass="text-[#5865F2]"
              />
            </div>
          </div>
        </>
      )}
    </div>
  );
};

interface ShareMenuItemProps {
  icon: string;
  label: string;
  onClick: () => void;
  iconClass?: string;
  highlight?: boolean;
  useCustomIcon?: boolean;
  customIcon?: React.ReactNode;
}

const ShareMenuItem: React.FC<ShareMenuItemProps> = ({
  icon,
  label,
  onClick,
  iconClass = '',
  highlight = false,
  useCustomIcon = false,
  customIcon,
}) => (
  <button
    type="button"
    onClick={onClick}
    className={`w-full flex items-center gap-3 px-3 py-2 text-sm rounded hover:bg-white/5 transition-colors ${
      highlight ? 'text-[#2DA66A]' : 'text-[#f0f2f5]'
    }`}
  >
    {useCustomIcon ? (
      customIcon
    ) : (
      <span className={`material-symbols-outlined text-[18px] ${iconClass}`}>{icon}</span>
    )}
    {label}
  </button>
);

export default ShareButton;
