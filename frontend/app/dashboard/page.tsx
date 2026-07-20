"use client";

import { CalendarDays, Clock3, LayoutDashboard, LoaderCircle, LogOut, UserRound } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { useAuth } from "@/features/auth/hooks/use-auth";
import { ProfileEditor } from "@/features/scheduling/components/profile-editor";
import { ScheduleEditor } from "@/features/scheduling/components/schedule-editor";

export default function DashboardPage() {
  const router = useRouter(); const { user, isLoading, logout } = useAuth();
  useEffect(() => { if (!isLoading && !user) router.replace("/login"); }, [isLoading, router, user]);
  if (isLoading || !user) return <main className="dashboard-loading"><LoaderCircle className="spin"/>Opening your calendar</main>;
  return <main className="workspace-shell"><aside className="workspace-nav"><Link href="/" className="wordmark">threecal<span>.</span></Link><nav><a className="selected"><LayoutDashboard/>Workspace</a><a><CalendarDays/>Event types</a><a><Clock3/>Bookings</a><a><UserRound/>Availability</a></nav><button onClick={async () => { await logout(); router.replace("/login"); }}><LogOut/>Sign out</button></aside><div className="workspace-content"><header><p className="kicker kicker-dark">Creator workspace</p><h1>Shape your<br/><em>bookable hours.</em></h1></header><ProfileEditor user={user}/><ScheduleEditor/></div></main>;
}
