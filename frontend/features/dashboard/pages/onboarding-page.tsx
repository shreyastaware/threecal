"use client";

import { ArrowRight, LoaderCircle } from "lucide-react";
import { useRouter } from "next/navigation";
import posthog from "posthog-js";
import { useEffect, useState } from "react";

import { useAuth } from "@/features/auth/hooks/use-auth";
import { DashboardHeader } from "@/features/dashboard/components/dashboard-header";
import { StatusMessage } from "@/features/dashboard/components/status-message";
import { ProfileEditor } from "@/features/scheduling/components/profile-editor";

export function OnboardingPage() {
  const router = useRouter();
  const { user, isLoading } = useAuth();
  const [completed, setCompleted] = useState(Boolean(user?.username));
  useEffect(() => {
    if (!isLoading && !user) router.replace("/login");
  }, [isLoading, router, user]);
  if (isLoading) return <main className="dashboard-loading"><LoaderCircle className="spin"/> Preparing your desk</main>;
  if (!user) return <main className="dashboard-loading">Redirecting to sign in</main>;
  return <main className="onboarding-canvas"><div className="onboarding-wrap"><DashboardHeader eyebrow="First, make it yours" title={<>Set up your<br/><em>public desk.</em></>} description="Choose the details people will see before they book time with you." /><StatusMessage tone="notice">Calendar integrations are not available in the current backend API. You can add your working hours next from Availability.</StatusMessage><ProfileEditor user={user} onSaved={(updated) => { const ready = Boolean(updated.username); setCompleted(ready); if (ready) { posthog.capture("onboarding_completed", { completion_method: "profile_saved" }); router.replace("/dashboard"); } }} /><button className="text-link onboarding-next" type="button" disabled={!completed && !user.username} onClick={() => { posthog.capture("onboarding_completed", { completion_method: "continue_button" }); router.replace("/dashboard"); }}>Continue to workspace <ArrowRight size={15}/></button></div></main>;
}
