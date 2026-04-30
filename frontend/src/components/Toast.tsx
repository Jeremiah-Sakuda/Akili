import React from 'react';
import { useToast, type ToastType } from '../contexts/ToastContext';

const ICON_MAP: Record<ToastType, string> = {
  error: 'error',
  success: 'check_circle',
  info: 'info',
};

const STYLE_MAP: Record<ToastType, string> = {
  error: 'bg-red-50 dark:bg-red-900/30 border-red-300 dark:border-red-700 text-red-800 dark:text-red-200',
  success: 'bg-emerald-50 dark:bg-emerald-900/30 border-emerald-300 dark:border-emerald-700 text-emerald-800 dark:text-emerald-200',
  info: 'bg-blue-50 dark:bg-blue-900/30 border-blue-300 dark:border-blue-700 text-blue-800 dark:text-blue-200',
};

const ToastContainer: React.FC = () => {
  const { toasts, removeToast } = useToast();

  if (toasts.length === 0) return null;

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-sm" aria-live="polite">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className={`flex items-start gap-2 px-4 py-3 border rounded-lg shadow-lg text-sm animate-in ${STYLE_MAP[toast.type]}`}
          role="alert"
        >
          <span className="material-symbols-outlined text-[18px] mt-0.5 shrink-0">
            {ICON_MAP[toast.type]}
          </span>
          <p className="flex-1 min-w-0">{toast.message}</p>
          <button
            type="button"
            onClick={() => removeToast(toast.id)}
            className="shrink-0 p-0.5 opacity-60 hover:opacity-100 transition-opacity"
            aria-label="Dismiss"
          >
            <span className="material-symbols-outlined text-[16px]">close</span>
          </button>
        </div>
      ))}
    </div>
  );
};

export default ToastContainer;
