"use client";

interface FormInputProps {
  id: string;
  label: string;
  type?: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  required?: boolean;
  disabled?: boolean;
  minLength?: number;
  autoComplete?: string;
}

export const FormInput = ({
  id,
  label,
  type = "text",
  value,
  onChange,
  placeholder,
  required,
  disabled,
  minLength,
  autoComplete,
}: FormInputProps) => (
  <div>
    <label htmlFor={id} className="mb-1.5 block text-sm font-medium text-slate-700">
      {label}
    </label>
    <input
      id={id}
      type={type}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      required={required}
      disabled={disabled}
      minLength={minLength}
      autoComplete={autoComplete}
      className="w-full rounded-lg border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 placeholder-slate-400 outline-none transition-colors focus:border-slate-400 focus:ring-2 focus:ring-slate-100 disabled:bg-slate-50 disabled:text-slate-500"
    />
  </div>
);
