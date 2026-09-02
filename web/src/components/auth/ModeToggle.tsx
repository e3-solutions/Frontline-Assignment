"use client";

type RegistrationMode = "company" | "user";

interface ModeToggleProps {
  mode: RegistrationMode;
  onModeChange: (mode: RegistrationMode) => void;
}

export const ModeToggle = ({ mode, onModeChange }: ModeToggleProps) => (
  <div className="mb-6 flex gap-1 rounded-lg bg-slate-100 p-1">
    <button
      type="button"
      onClick={() => onModeChange("company")}
      className={`flex-1 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
        mode === "company"
          ? "bg-white text-slate-900 shadow-sm"
          : "text-slate-600 hover:text-slate-900"
      }`}
    >
      New Company
    </button>
    <button
      type="button"
      onClick={() => onModeChange("user")}
      className={`flex-1 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
        mode === "user"
          ? "bg-white text-slate-900 shadow-sm"
          : "text-slate-600 hover:text-slate-900"
      }`}
    >
      Join via Invite
    </button>
  </div>
);
