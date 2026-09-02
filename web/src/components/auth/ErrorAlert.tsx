"use client";

interface ErrorAlertProps {
  message: string;
}

export const ErrorAlert = ({ message }: ErrorAlertProps) => (
  <div className="mb-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-600">
    {message}
  </div>
);
