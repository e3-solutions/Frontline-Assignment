"use client";

import { EyeIcon, EyeOffIcon } from "./icons";

interface PasswordInputProps {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  showPassword: boolean;
  onToggleShow: () => void;
  placeholder?: string;
  autoComplete?: string;
}

export const PasswordInput = ({
  id,
  label,
  value,
  onChange,
  showPassword,
  onToggleShow,
  placeholder = "••••••••",
  autoComplete = "new-password",
}: PasswordInputProps) => (
  <div>
    <label htmlFor={id} className="mb-1.5 block text-sm font-medium text-slate-700">
      {label}
    </label>
    <div className="relative">
      <input
        id={id}
        type={showPassword ? "text" : "password"}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        autoComplete={autoComplete}
        required
        minLength={6}
        className="w-full rounded-lg border border-slate-200 bg-white px-4 py-3 pr-10 text-sm text-slate-900 placeholder-slate-400 outline-none transition-colors focus:border-slate-400 focus:ring-2 focus:ring-slate-100"
      />
      <button
        type="button"
        onClick={onToggleShow}
        className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
      >
        {showPassword ? <EyeOffIcon /> : <EyeIcon />}
      </button>
    </div>
  </div>
);
