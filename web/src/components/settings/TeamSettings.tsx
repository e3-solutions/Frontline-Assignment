"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { useAuth } from "@/src/contexts/AuthContext";
import { invitesService } from "@/src/services/supabase/invites";
import { usersService } from "@/src/services/supabase/users";
import { InviteForm, InviteLinkDisplay, InviteList, MemberList, CreateAccountForm } from "./team";
import type { Invite, User } from "@/src/types/auth";

interface TeamData {
  invites: Invite[];
  members: User[];
  isLoading: boolean;
}

interface Feedback {
  error: string | null;
  success: string | null;
}

export function TeamSettings() {
  const { user, organization, isLoading: authLoading } = useAuth();
  const [data, setData] = useState<TeamData>({
    invites: [],
    members: [],
    isLoading: true,
  });
  const [feedback, setFeedback] = useState<Feedback>({
    error: null,
    success: null,
  });
  const [generatedLink, setGeneratedLink] = useState<string | null>(null);
  const [createdCredentials, setCreatedCredentials] = useState<{
    email: string;
    password: string;
  } | null>(null);

  const loadData = useCallback(async () => {
    if (!organization) return;

    setData((prev) => ({ ...prev, isLoading: true }));
    try {
      const [invitesResult, membersResult] = await Promise.all([
        invitesService.getByOrgId(organization.id),
        usersService.getByOrgId(organization.id),
      ]);

      setData({
        invites: invitesResult.data || [],
        members: membersResult.data || [],
        isLoading: false,
      });
    } catch {
      setFeedback({ error: "Failed to load team data", success: null });
      setData((prev) => ({ ...prev, isLoading: false }));
    }
  }, [organization]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleInviteSuccess = (email: string, link: string) => {
    setGeneratedLink(link);
    setFeedback({ error: null, success: `Invitation created for ${email}` });
    loadData();
  };

  const handleAccountCreated = (email: string, password: string) => {
    setCreatedCredentials({ email, password });
    setFeedback({ error: null, success: `Account created for ${email}` });
    loadData();
  };

  const copyCredentials = async () => {
    if (!createdCredentials) return;
    const text = `Email: ${createdCredentials.email}\nPassword: ${createdCredentials.password}`;
    try {
      await navigator.clipboard.writeText(text);
      setFeedback({ error: null, success: "Credentials copied to clipboard!" });
    } catch {
      setFeedback({ error: "Failed to copy credentials", success: null });
    }
  };

  const handleDeleteInvite = async (inviteId: string) => {
    try {
      await invitesService.delete(inviteId);
      setData((prev) => ({
        ...prev,
        invites: prev.invites.filter((i) => i.id !== inviteId),
      }));
      setFeedback({ error: null, success: "Invite deleted" });
    } catch {
      setFeedback({ error: "Failed to delete invite", success: null });
    }
  };

  const copyToClipboard = async () => {
    if (!generatedLink) return;
    try {
      await navigator.clipboard.writeText(generatedLink);
      setFeedback({ error: null, success: "Link copied to clipboard!" });
    } catch {
      setFeedback({ error: "Failed to copy link", success: null });
    }
  };

  if (authLoading) {
    return null;
  }

  if (user?.role !== "admin") {
    return (
      <div className="mx-auto max-w-4xl px-4 py-8">
        <div className="rounded-lg border border-[color:var(--e3-chip-rose-border)] bg-[color:var(--e3-chip-rose-bg)] p-4 text-sm text-[color:var(--e3-chip-rose-text)]">
          You don&apos;t have permission to access this page.
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[color:var(--e3-bg-app)]">
      <div className="mx-auto max-w-4xl px-4 py-8">
        {/* Header */}
        <div className="mb-8">
          <Link
            href="/"
            className="mb-4 inline-flex items-center gap-2 text-sm text-[color:var(--e3-text-muted)] hover:text-[color:var(--e3-text-strong)]"
          >
            <svg
              className="h-4 w-4"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M15 19l-7-7 7-7"
              />
            </svg>
            Back to Dashboard
          </Link>
          <h1 className="text-2xl font-semibold text-[color:var(--e3-text-strong)]">
            Team Settings
          </h1>
          <p className="mt-1 text-sm text-[color:var(--e3-text-soft)]">
            Manage your team members and invitations for {organization?.name}
          </p>
        </div>

        {/* Alerts */}
        {feedback.error && (
          <div className="mb-4 rounded-lg border border-[color:var(--e3-chip-rose-border)] bg-[color:var(--e3-chip-rose-bg)] p-3 text-sm text-[color:var(--e3-chip-rose-text)]">
            {feedback.error}
          </div>
        )}
        {feedback.success && (
          <div className="mb-4 rounded-lg border border-[color:var(--e3-chip-success-border)] bg-[color:var(--e3-chip-success-bg)] p-3 text-sm text-[color:var(--e3-chip-success-text)]">
            {feedback.success}
          </div>
        )}

        <InviteForm
          orgId={organization?.id || ""}
          onSuccess={handleInviteSuccess}
          onError={(msg) => setFeedback({ error: msg, success: null })}
        />

        {generatedLink && (
          <InviteLinkDisplay link={generatedLink} onCopy={copyToClipboard} />
        )}

        <CreateAccountForm
          orgId={organization?.id || ""}
          onSuccess={handleAccountCreated}
          onError={(msg) => setFeedback({ error: msg, success: null })}
        />

        {createdCredentials && (
          <div className="mb-8 rounded-lg border border-[color:var(--e3-border-soft)] bg-[color:var(--e3-surface-soft)] p-4">
            <p className="mb-2 text-sm font-medium text-[color:var(--e3-text-muted)]">
              Account Credentials
            </p>
            <div className="space-y-1 rounded-lg border border-[color:var(--e3-border-subtle)] bg-[color:var(--e3-shell)] px-4 py-3">
              <p className="text-sm text-[color:var(--e3-text-muted)]">
                <span className="font-medium">Email:</span>{" "}
                <span className="font-mono text-[color:var(--e3-text-strong)]">{createdCredentials.email}</span>
              </p>
              <p className="text-sm text-[color:var(--e3-text-muted)]">
                <span className="font-medium">Password:</span>{" "}
                <span className="font-mono text-[color:var(--e3-text-strong)]">{createdCredentials.password}</span>
              </p>
            </div>
            <button
              type="button"
              onClick={copyCredentials}
              className="mt-3 rounded-lg border border-[color:var(--e3-border-soft)] bg-[color:var(--e3-shell)] px-4 py-2 text-sm font-medium text-[color:var(--e3-text-muted)] hover:bg-[color:var(--e3-surface-alt)] hover:text-[color:var(--e3-text-strong)]"
            >
              Copy Credentials
            </button>
            <p className="mt-2 text-xs text-[color:var(--e3-text-soft)]">
              Share these credentials with the client so they can sign in.
            </p>
          </div>
        )}

        <InviteList
          invites={data.invites}
          isLoading={data.isLoading}
          onDelete={handleDeleteInvite}
        />

        <MemberList
          members={data.members}
          currentUserId={user?.user_id}
          isLoading={data.isLoading}
        />
      </div>
    </div>
  );
}
