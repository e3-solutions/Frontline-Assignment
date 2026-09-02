"use client";

import { SpinnerIcon } from "./icons";

interface LoadingSpinnerProps {
  className?: string;
}

export const LoadingSpinner = ({ className = "h-8 w-8 text-slate-400" }: LoadingSpinnerProps) => (
  <SpinnerIcon className={className} />
);
