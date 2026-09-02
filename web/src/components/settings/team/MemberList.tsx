"use client";

import type { User } from "@/src/types/auth";

interface MemberListProps {
  members: User[];
  currentUserId?: string;
  isLoading: boolean;
}

function getInitials(name: string): string {
  return name
    .split(" ")
    .map((n) => n[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);
}

export function MemberList({
  members,
  currentUserId,
  isLoading,
}: MemberListProps) {
  return (
    <div className="rounded-xl border border-[color:var(--e3-border-soft)] bg-[color:var(--e3-shell)] p-6">
      <h2 className="mb-4 text-lg font-medium text-[color:var(--e3-text-strong)]">Team Members</h2>
      {isLoading ? (
        <p className="text-sm text-[color:var(--e3-text-soft)]">Loading...</p>
      ) : members.length === 0 ? (
        <p className="text-sm text-[color:var(--e3-text-soft)]">No team members</p>
      ) : (
        <div className="space-y-3">
          {members.map((member) => (
            <div
              key={member.user_id}
              className="flex items-center justify-between rounded-lg border border-[color:var(--e3-border-subtle)] bg-[color:var(--e3-surface-soft)] p-3"
            >
              <div className="flex items-center gap-3">
                <div className="flex h-8 w-8 items-center justify-center rounded-full bg-[color:var(--e3-brand-accent)] text-xs font-semibold text-white">
                  {getInitials(member.full_name)}
                </div>
                <div>
                  <span className="text-sm font-medium text-[color:var(--e3-text-strong)]">
                    {member.full_name}
                  </span>
                  {member.user_id === currentUserId && (
                    <span className="ml-2 text-xs text-[color:var(--e3-text-soft)]">(you)</span>
                  )}
                </div>
                <span className="rounded bg-[color:var(--e3-surface-alt)] px-2 py-0.5 text-xs font-medium capitalize text-[color:var(--e3-text-muted)]">
                  {member.role}
                </span>
                {member.is_superadmin && (
                  <span className="rounded border border-[color:var(--e3-chip-violet-border)] bg-[color:var(--e3-chip-violet-bg)] px-2 py-0.5 text-xs font-medium text-[color:var(--e3-chip-violet-text)]">
                    Superadmin
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
