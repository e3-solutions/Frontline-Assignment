"use client";

import type { Invite } from "@/src/types/auth";

interface InviteListProps {
  invites: Invite[];
  isLoading: boolean;
  onDelete: (inviteId: string) => void;
}

export function InviteList({ invites, isLoading, onDelete }: InviteListProps) {
  return (
    <div className="mb-8 rounded-xl border border-[color:var(--e3-border-soft)] bg-[color:var(--e3-shell)] p-6">
      <h2 className="mb-4 text-lg font-medium text-[color:var(--e3-text-strong)]">
        Pending Invitations
      </h2>
      {isLoading ? (
        <p className="text-sm text-[color:var(--e3-text-soft)]">Loading...</p>
      ) : invites.length === 0 ? (
        <p className="text-sm text-[color:var(--e3-text-soft)]">No pending invitations</p>
      ) : (
        <div className="space-y-3">
          {invites.map((invite) => (
            <div
              key={invite.id}
              className="flex items-center justify-between rounded-lg border border-[color:var(--e3-border-subtle)] bg-[color:var(--e3-surface-soft)] p-3"
            >
              <div className="flex items-center gap-3">
                <span className="text-sm font-medium text-[color:var(--e3-text-strong)]">
                  {invite.email}
                </span>
                <span className="rounded bg-[color:var(--e3-surface-alt)] px-2 py-0.5 text-xs font-medium capitalize text-[color:var(--e3-text-muted)]">
                  {invite.role}
                </span>
                <span className="text-xs text-[color:var(--e3-text-soft)]">
                  Expires {new Date(invite.expires_at).toLocaleDateString()}
                </span>
              </div>
              <button
                type="button"
                onClick={() => onDelete(invite.id)}
                className="text-sm text-[color:var(--e3-chip-rose-text)] hover:opacity-80"
              >
                Delete
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
