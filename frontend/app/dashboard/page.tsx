"use client";

import { ArrowUpRight, CalendarDays, LoaderCircle, LogOut } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { useAuth } from "@/features/auth/hooks/use-auth";

export default function DashboardPage() {
  const router = useRouter();
  const { user, isLoading, logout } = useAuth();

  useEffect(() => {
    if (!isLoading && !user) router.replace("/login");
  }, [isLoading, router, user]);

  if (isLoading || !user) {
    return (
      <main className="dashboard-loading">
        <LoaderCircle className="spin" />
        <span>Opening your calendar</span>
      </main>
    );
  }

  const firstName = user.full_name.split(" ")[0];

  return (
    <main className="dashboard-shell">
      <aside className="dashboard-rail">
        <Link href="/" className="wordmark">
          threecal<span>.</span>
        </Link>
        <div className="rail-mark">
          <CalendarDays size={20} />
        </div>
        <button
          className="rail-logout"
          onClick={async () => {
            await logout();
            router.replace("/login");
          }}
          aria-label="Sign out"
        >
          <LogOut size={18} />
        </button>
      </aside>
      <section className="dashboard-content">
        <p className="kicker kicker-dark">Private workspace · Phase 1</p>
        <h1>Good to see you, {firstName}.</h1>
        <p className="dashboard-lede">
          Your authentication foundation is connected. Profile setup,
          availability, and calendar integrations arrive in Phase 2.
        </p>
        <div className="dashboard-card">
          <span>Signed in as</span>
          <strong>{user.email}</strong>
          <i className={user.is_email_verified ? "verified" : "pending"}>
            {user.is_email_verified ? "Verified" : "Verification pending"}
          </i>
        </div>
        <Link href="/" className="text-link">
          Back to threecal <ArrowUpRight size={15} />
        </Link>
      </section>
    </main>
  );
}
