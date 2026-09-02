"use client";

interface InviteLinkDisplayProps {
  link: string;
  onCopy: () => void;
}

export function InviteLinkDisplay({ link, onCopy }: InviteLinkDisplayProps) {
  return (
    <div className="mb-8 rounded-lg border border-[color:var(--e3-border-soft)] bg-[color:var(--e3-surface-soft)] p-4">
      <p className="mb-2 text-sm font-medium text-[color:var(--e3-text-muted)]">Invitation Link</p>
      <div className="flex gap-2">
        <input
          type="text"
          readOnly
          value={link}
          className="flex-1 rounded-lg border border-[color:var(--e3-border-subtle)] bg-[color:var(--e3-shell)] px-3 py-2 text-sm text-[color:var(--e3-text-muted)]"
        />
        <button
          type="button"
          onClick={onCopy}
          className="rounded-lg border border-[color:var(--e3-border-soft)] bg-[color:var(--e3-shell)] px-4 py-2 text-sm font-medium text-[color:var(--e3-text-muted)] hover:bg-[color:var(--e3-surface-alt)] hover:text-[color:var(--e3-text-strong)]"
        >
          Copy
        </button>
      </div>
      <p className="mt-2 text-xs text-[color:var(--e3-text-soft)]">This link expires in 7 days</p>
    </div>
  );
}
