"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { AuthLayout } from "./AuthLayout";
import { ModeToggle } from "./ModeToggle";
import { ErrorAlert } from "./ErrorAlert";
import { LoadingSpinner } from "./LoadingSpinner";
import { CompanyForm } from "./CompanyForm";
import { InviteForm } from "./InviteForm";
import { validateInvite } from "@/src/services/auth";

type RegistrationMode = "company" | "user";

export const Register = () => {
  const router = useRouter();
  const searchParams = useSearchParams();
  const inviteToken = searchParams.get("invite");

  const [mode, setMode] = useState<RegistrationMode>(inviteToken ? "user" : "company");
  const [error, setError] = useState<string | null>(null);
  const [inviteEmail, setInviteEmail] = useState<string | null>(null);
  const [isValidatingInvite, setIsValidatingInvite] = useState(!!inviteToken);

  useEffect(() => {
    if (!inviteToken) return;

    setIsValidatingInvite(true);
    validateInvite(inviteToken)
      .then((data) => {
        if (data) {
          setInviteEmail(data.email);
          setMode("user");
        } else {
          setError("Invalid or expired invitation link");
          setMode("company");
        }
      })
      .catch(() => {
        setError("Failed to validate invitation");
        setMode("company");
      })
      .finally(() => setIsValidatingInvite(false));
  }, [inviteToken]);

  const handleSuccess = () => {
    router.push("/");
    router.refresh();
  };

  const handleModeChange = (newMode: RegistrationMode) => {
    setMode(newMode);
    setError(null);
  };

  if (isValidatingInvite) {
    return (
      <AuthLayout subtitle="Validating invitation...">
        <div className="flex items-center justify-center py-12">
          <LoadingSpinner />
        </div>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout
      subtitle={mode === "company" ? "Create your organization" : "Join an organization"}
    >
      {!inviteToken && <ModeToggle mode={mode} onModeChange={handleModeChange} />}

      {error && <ErrorAlert message={error} />}

      {mode === "company" ? (
        <CompanyForm onError={setError} onSuccess={handleSuccess} />
      ) : (
        <InviteForm
          inviteToken={inviteToken}
          inviteEmail={inviteEmail}
          onError={setError}
          onSuccess={handleSuccess}
        />
      )}

      <p className="mt-6 text-center text-sm text-slate-500">
        Already have an account?{" "}
        <Link href="/login" className="font-medium text-slate-900 hover:underline">
          Sign in
        </Link>
      </p>
    </AuthLayout>
  );
};
