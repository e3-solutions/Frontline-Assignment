"use client";

import { useState } from "react";
import { createInvite } from "@/src/services/auth";
import type { UserRole } from "@/src/types/auth";

interface InviteFormProps {
  orgId: string;
  onSuccess: (email: string, link: string) => void;
  onError: (message: string) => void;
}

export function InviteForm({ orgId, onSuccess, onError }: InviteFormProps) {
  const [form, setForm] = useState({ email: "", role: "employee" as UserRole });
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);

    try {
      const result = await createInvite({
        orgId,
        email: form.email,
        role: form.role,
      });

      const inviteLink = `${window.location.origin}/register?invite=${result.token}`;
      onSuccess(form.email, inviteLink);
      setForm({ email: "", role: "employee" });
    } catch (err) {
      onError(err instanceof Error ? err.message : "Failed to create invite");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="mb-8 rounded-xl border border-[color:var(--e3-border-soft)] bg-[color:var(--e3-shell)] p-6">
      <h2 className="mb-4 text-lg font-medium text-[color:var(--e3-text-strong)]">
        Invite Team Member
      </h2>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div className="sm:col-span-2">
            <label
              htmlFor="email"
              className="mb-1.5 block text-sm font-medium text-[color:var(--e3-text-muted)]"
            >
              Email Address
            </label>
            <input
              id="email"
              type="email"
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
              placeholder="colleague@example.com"
              required
              className="w-full rounded-lg border border-[color:var(--e3-border-soft)] bg-[color:var(--e3-surface-soft)] px-3 py-2.5 text-sm text-[color:var(--e3-text-strong)] placeholder-[color:var(--e3-text-soft)] outline-none transition-colors focus:border-[color:var(--e3-border-strong)] focus:ring-2 focus:ring-[rgba(143,108,255,0.25)]"
            />
          </div>
          <div>
            <label
              htmlFor="role"
              className="mb-1.5 block text-sm font-medium text-[color:var(--e3-text-muted)]"
            >
              Role
            </label>
            <select
              id="role"
              value={form.role}
              onChange={(e) =>
                setForm({ ...form, role: e.target.value as UserRole })
              }
              className="w-full rounded-lg border border-[color:var(--e3-border-soft)] bg-[color:var(--e3-surface-soft)] px-3 py-2.5 text-sm text-[color:var(--e3-text-strong)] outline-none transition-colors focus:border-[color:var(--e3-border-strong)] focus:ring-2 focus:ring-[rgba(143,108,255,0.25)]"
            >
              <option value="employee">Employee</option>
              <option value="admin">Admin</option>
            </select>
          </div>
        </div>
        <button
          type="submit"
          disabled={isSubmitting}
          className="rounded-lg bg-[color:var(--e3-brand-accent)] px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-[color:var(--e3-brand-deep)] disabled:cursor-not-allowed disabled:opacity-50"
        >
          {isSubmitting ? "Creating..." : "Create Invitation"}
        </button>
      </form>
    </div>
  );
}
