"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { AuthLayout } from "./AuthLayout";
import { FormInput } from "./FormInput";
import { PasswordInput } from "./PasswordInput";
import { SubmitButton } from "./SubmitButton";
import { ErrorAlert } from "./ErrorAlert";
import { login } from "@/src/services/auth";

export const Login = () => {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsLoading(true);

    try {
      await login({ email, password });
      router.push("/");
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <AuthLayout subtitle="Sign in to your account">
      {error && <ErrorAlert message={error} />}

      <form onSubmit={handleSubmit} className="space-y-4">
        <FormInput
          id="email"
          label="Email"
          type="email"
          value={email}
          onChange={setEmail}
          placeholder="you@example.com"
          autoComplete="email"
          required
        />

        <PasswordInput
          id="password"
          label="Password"
          value={password}
          onChange={setPassword}
          showPassword={showPassword}
          onToggleShow={() => setShowPassword(!showPassword)}
          autoComplete="current-password"
        />

        <SubmitButton isLoading={isLoading} loadingText="Signing in...">
          Sign In
        </SubmitButton>
      </form>

      <p className="mt-6 text-center text-sm text-slate-500">
        Don&apos;t have an account?{" "}
        <Link href="/register" className="font-medium text-slate-900 hover:underline">
          Create one
        </Link>
      </p>
    </AuthLayout>
  );
};
