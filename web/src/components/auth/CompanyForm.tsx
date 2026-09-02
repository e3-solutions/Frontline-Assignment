"use client";

import { useState } from "react";
import { FormInput } from "./FormInput";
import { PasswordInput } from "./PasswordInput";
import { SubmitButton } from "./SubmitButton";
import { useRegistrationForm } from "./useRegistrationForm";
import { registerCompany } from "@/src/services/auth";

interface CompanyFormProps {
  onError: (error: string | null) => void;
  onSuccess: () => void;
}

export const CompanyForm = ({ onError, onSuccess }: CompanyFormProps) => {
  const { form, updateField, toggleShowPassword, setLoading, validatePasswords } =
    useRegistrationForm();
  const [organizationName, setOrganizationName] = useState("");
  const [companySecret, setCompanySecret] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    onError(null);

    if (!validatePasswords()) {
      onError("Passwords do not match");
      return;
    }

    setLoading(true);
    try {
      await registerCompany({
        email: form.email,
        password: form.password,
        fullName: form.fullName,
        organizationName,
        companySecret,
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
        />
      </div>

      <div className="grid grid-cols-2 gap-5">
        <FormInput
          id="organizationName"
          label="Organization Name"
          value={organizationName}
          onChange={setOrganizationName}
          placeholder="Acme Inc."
          required
          minLength={2}
        />
        <FormInput
          id="companySecret"
          label="Registration Code"
          type="password"
          value={companySecret}
          onChange={setCompanySecret}
          placeholder="••••••••"
          required
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

      <SubmitButton isLoading={form.isLoading} loadingText="Creating Organization...">
        Create Organization
      </SubmitButton>
    </form>
  );
};
