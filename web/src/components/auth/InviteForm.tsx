"use client";

import { FormInput } from "./FormInput";
import { PasswordInput } from "./PasswordInput";
import { SubmitButton } from "./SubmitButton";
import { useRegistrationForm } from "./useRegistrationForm";
import { registerUser } from "@/src/services/auth";

interface InviteFormProps {
  inviteToken: string | null;
  inviteEmail: string | null;
  onError: (error: string | null) => void;
  onSuccess: () => void;
}

export const InviteForm = ({
  inviteToken,
  inviteEmail,
  onError,
  onSuccess,
}: InviteFormProps) => {
  const { form, updateField, toggleShowPassword, setLoading, validatePasswords } =
    useRegistrationForm(inviteEmail || "");

  if (!inviteToken) {
    return (
      <div className="py-8 text-center">
        <p className="text-sm text-slate-600">
          To join an existing organization, you need an invitation link.
        </p>
        <p className="mt-2 text-sm text-slate-500">
          Please ask your organization admin to send you an invite.
        </p>
      </div>
    );
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    onError(null);

    if (!validatePasswords()) {
      onError("Passwords do not match");
      return;
    }

    setLoading(true);
    try {
      await registerUser({
        email: form.email,
        password: form.password,
        fullName: form.fullName,
        inviteToken,
      });
      onSuccess();
    } catch (err) {
      onError(err instanceof Error ? err.message : "Registration failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      <div className="grid grid-cols-2 gap-5">
        <FormInput
          id="fullName"
          label="Full Name"
          value={form.fullName}
          onChange={(v) => updateField("fullName", v)}
          placeholder="John Doe"
          required
          minLength={2}
        />
        <FormInput
          id="email"
          label="Email"
          type="email"
          value={form.email}
          onChange={(v) => updateField("email", v)}
          placeholder="you@example.com"
          autoComplete="email"
          required
          disabled={!!inviteEmail}
        />
      </div>

      <div className="grid grid-cols-2 gap-5">
        <PasswordInput
          id="password"
          label="Password"
          value={form.password}
          onChange={(v) => updateField("password", v)}
          showPassword={form.showPassword}
          onToggleShow={toggleShowPassword}
        />
        <FormInput
          id="confirmPassword"
          label="Confirm Password"
          type={form.showPassword ? "text" : "password"}
          value={form.confirmPassword}
          onChange={(v) => updateField("confirmPassword", v)}
          placeholder="••••••••"
          autoComplete="new-password"
          required
          minLength={6}
        />
      </div>

      <SubmitButton isLoading={form.isLoading} loadingText="Joining Organization...">
        Join Organization
      </SubmitButton>
    </form>
  );
};
