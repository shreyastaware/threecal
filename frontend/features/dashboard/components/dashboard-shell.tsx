"use client";

import { Menu } from "@base-ui/react/menu";
import {
  CalendarDays,
  ChevronUp,
  Landmark,
  LayoutDashboard,
  Link2,
  LoaderCircle,
  LogOut,
  Settings2,
  UserRound,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";

import { useAuth } from "@/features/auth/hooks/use-auth";

const navigation = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/dashboard/event-types", label: "Event types", icon: Link2 },
  { href: "/dashboard/bookings", label: "Bookings", icon: CalendarDays },
  { href: "/dashboard/payments", label: "Payments", icon: Landmark },
  { href: "/dashboard/availability", label: "Availability", icon: Settings2 },
];

export function DashboardShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, isLoading, logout } = useAuth();

  useEffect(() => {
    if (!isLoading && !user) router.replace("/login");
    if (!isLoading && user && !user.username && pathname !== "/dashboard/profile") router.replace("/onboarding");
  }, [isLoading, pathname, router, user]);

  if (isLoading || !user) {
    return (
      <main className="dashboard-loading">
        <LoaderCircle className="spin" /> Opening your workspace
      </main>
    );
  }

  async function signOut() {
    await logout();
    router.replace("/login");
  }

  return (
    <main className="workspace-shell">
      <aside className="workspace-nav">
        <Link href="/" className="wordmark">
          threecal<span>.</span>
        </Link>
        <nav aria-label="Workspace navigation">
          {navigation.map(({ href, label, icon: Icon }) => {
            const active = href === "/dashboard"
              ? pathname === href
              : pathname.startsWith(href);
            return (
              <Link className={active ? "selected" : ""} href={href} key={href}>
                <Icon /> {label}
              </Link>
            );
          })}
        </nav>
        <div className="workspace-nav-footer">
          <Menu.Root modal={false}>
            <Menu.Trigger
              className="workspace-user-trigger"
              type="button"
            >
              <UserRound />
              <span>{user.full_name}</span>
              <ChevronUp className="workspace-user-chevron" />
            </Menu.Trigger>
            <Menu.Portal>
              <Menu.Positioner
                align="start"
                className="workspace-user-menu-positioner"
                side="top"
                sideOffset={8}
              >
                <Menu.Popup className="workspace-user-menu">
                  <Menu.LinkItem
                    className="workspace-user-menu-item"
                    closeOnClick
                    render={<Link href="/dashboard/profile" />}
                  >
                    <UserRound /> Profile
                  </Menu.LinkItem>
                  <Menu.Item
                    className="workspace-user-menu-item workspace-user-menu-signout"
                    nativeButton
                    onClick={signOut}
                    render={<button type="button" />}
                  >
                    <LogOut /> Sign out
                  </Menu.Item>
                </Menu.Popup>
              </Menu.Positioner>
            </Menu.Portal>
          </Menu.Root>
        </div>
      </aside>
      <div className="workspace-content">{children}</div>
    </main>
  );
}
