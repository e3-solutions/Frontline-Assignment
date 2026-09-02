"use client";

import { LoadingSpinner } from "./LoadingSpinner";

interface SubmitButtonProps {
  isLoading: boolean;
  loadingText: string;
  children: React.ReactNode;
}

export const SubmitButton = ({ isLoading, loadingText, children }: SubmitButtonProps) => (
  <button
    type="submit"
    disabled={isLoading}
    className="mt-4 w-full rounded-lg bg-slate-900 px-5 py-3.5 text-sm font-semibold text-white transition-colors hover:bg-slate-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-600 disabled:cursor-not-allowed disabled:opacity-50"
  >
    {isLoading ? (
      <span className="flex items-center justify-center gap-2">
        <LoadingSpinner className="h-4 w-4" />
        {loadingText}
      </span>
    ) : (
      children
    )}
  </button>
);
