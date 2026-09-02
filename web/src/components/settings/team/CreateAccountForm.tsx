"use client";

import { useState } from "react";
import { createUserAccount } from "@/src/services/auth";
import type { UserRole } from "@/src/types/auth";

interface CreateAccountFormProps {
  orgId: string;
  onSuccess: (email: string, password: string) => void;
  onError: (message: string) => void;
}

const generatePassword = (): string => {
  const chars = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789";
  const symbols = "!@#$%&*";
  let password = "";
  for (let i = 0; i < 12; i++) {
    password += chars[Math.floor(Math.random() * chars.length)];
  }
  password += symbols[Math.floor(Math.random() * symbols.length)];
  return password;
};

export function CreateAccountForm({ orgId, onSuccess, onError }: CreateAccountFormProps) {
  const [form, setForm] = useState({
    email: "",
    fullName: "",
    password: generatePassword(),
    role: "employee" as UserRole,
  });
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);

    try {
      await createUserAccount({
        email: form.email,
        password: form.password,
        fullName: form.fullName,
        role: form.role,
        orgId,
      });
      const createdPassword = form.password;
      const createdEmail = form.email;
      setForm({ email: "", fullName: "", password: generatePassword(), role: "employee" });
      onSuccess(createdEmail, createdPassword);
    } catch (err) {
      onError(err instanceof Error ? err.message : "Failed to create account");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="mb-8 rounded-xl border border-[color:var(--e3-border-soft)] bg-[color:var(--e3-shell)] p-6">
      <h2 className="mb-1 text-lg font-medium text-[color:var(--e3-text-strong)]">Create Account</h2>
      <p className="mb-4 text-sm text-[color:var(--e3-text-soft)]">
        Create a login directly — share the credentials with the client.
      </p>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <label htmlFor="ca-email" className="mb-1.5 block text-sm font-medium text-[color:var(--e3-text-muted)]">
              Email Address
            </label>
            <input
              id="ca-email"
              type="email"
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
              placeholder="client@example.com"
              required
              className="w-full rounded-lg border border-[color:var(--e3-border-soft)] bg-[color:var(--e3-surface-soft)] px-3 py-2.5 text-sm text-[color:var(--e3-text-strong)] placeholder-[color:var(--e3-text-soft)] outline-none transition-colors focus:border-[color:var(--e3-border-strong)] focus:ring-2 focus:ring-[rgba(143,108,255,0.25)]"
            />
          </div>
          <div>
            <label htmlFor="ca-name" className="mb-1.5 block text-sm font-medium text-[color:var(--e3-text-muted)]">
              Full Name
            </label>
            <input
              id="ca-name"
              type="text"
              value={form.fullName}
              onChange={(e) => setForm({ ...form, fullName: e.target.value })}
              placeholder="Jane Smith"
              required
              className="w-full rounded-lg border border-[color:var(--e3-border-soft)] bg-[color:var(--e3-surface-soft)] px-3 py-2.5 text-sm text-[color:var(--e3-text-strong)] placeholder-[color:var(--e3-text-soft)] outline-none transition-colors focus:border-[color:var(--e3-border-strong)] focus:ring-2 focus:ring-[rgba(143,108,255,0.25)]"
            />
          </div>
        </div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div className="sm:col-span-2">
            <label htmlFor="ca-password" className="mb-1.5 block text-sm font-medium text-[color:var(--e3-text-muted)]">
              Password
            </label>
            <div className="flex gap-2">
              <input
                id="ca-password"
                type="text"
                value={form.password}
                onChange={(e) => setForm({ ...form, password: e.target.value })}
                required
                minLength={8}
                className="flex-1 rounded-lg border border-[color:var(--e3-border-soft)] bg-[color:var(--e3-surface-soft)] px-3 py-2.5 font-mono text-sm text-[color:var(--e3-text-strong)] outline-none transition-colors focus:border-[color:var(--e3-border-strong)] focus:ring-2 focus:ring-[rgba(143,108,255,0.25)]"
              />
              <button
                type="button"
                onClick={() => setForm({ ...form, password: generatePassword() })}
                className="shrink-0 rounded-lg border border-[color:var(--e3-border-soft)] bg-[color:var(--e3-surface-soft)] px-3 py-2.5 text-sm font-medium text-[color:var(--e3-text-muted)] hover:bg-[color:var(--e3-surface-alt)] hover:text-[color:var(--e3-text-strong)]"
              >
                Generate
              </button>
            </div>
          </div>
          <div>
            <label htmlFor="ca-role" className="mb-1.5 block text-sm font-medium text-[color:var(--e3-text-muted)]">
              Role
            </label>
            <select
              id="ca-role"
              value={form.role}
              onChange={(e) => setForm({ ...form, role: e.target.value as UserRole })}
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
          {isSubmitting ? "Creating..." : "Create Account"}
        </button>
      </form>
    </div>
  );
}
