"use client";

import { useState, useRef, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/src/contexts/AuthContext";

export function UserMenu() {
  const { user, organization, logout } = useAuth();
  const [isOpen, setIsOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const router = useRouter();

  // Close menu when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Get user initials
  const initials = user?.full_name
    ? user.full_name
        .split(" ")
        .map((n) => n[0])
        .join("")
        .toUpperCase()
        .slice(0, 2)
    : "U";

  const handleLogout = async () => {
    await logout();
    setIsOpen(false);
    router.push("/login");
    router.refresh();
  };

  return (
    <div className="relative" ref={menuRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex h-9 w-9 items-center justify-center rounded-full bg-slate-900 text-sm font-semibold text-white transition-transform hover:scale-105"
      >
        {initials}
      </button>

      {isOpen && (
        <div className="absolute bottom-full left-0 z-50 mb-2 min-w-[220px] rounded-lg border border-[color:var(--e3-border-soft)] bg-[color:var(--e3-shell)] p-1 shadow-lg">
          <div className="border-b border-[color:var(--e3-border-subtle)] px-3 py-2">
            <p className="text-sm font-medium text-[color:var(--e3-text-strong)]">
              {user?.full_name}
            </p>
            <p className="text-xs text-[color:var(--e3-text-soft)]">{organization?.name}</p>
          </div>

          <div className="py-1">
            {user?.role === "admin" && (
              <Link
                href="/settings/team"
                onClick={() => setIsOpen(false)}
                className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm text-[color:var(--e3-text-muted)] hover:bg-[color:var(--e3-surface-soft)] hover:text-[color:var(--e3-text-strong)]"
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
                    d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z"
                  />
                </svg>
                Team Settings
              </Link>
            )}

            <button
              onClick={handleLogout}
              className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm text-[color:var(--e3-text-muted)] hover:bg-[color:var(--e3-surface-soft)] hover:text-[color:var(--e3-text-strong)]"
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
                  d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"
                />
              </svg>
              Sign Out
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
