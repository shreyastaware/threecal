import { redirect } from "next/navigation";

import { bookingApi } from "@/features/booking/api";
import { PublicProfile } from "@/features/booking/components/public-profile";

export default async function PublicProfilePage({
  params,
}: {
  params: Promise<{ username: string }>;
}) {
  const { username } = await params;
  const initialProfile = await bookingApi.getProfile(username).catch(() => undefined);

  if (initialProfile?.default_event_type_slug) {
    redirect(
      `/${encodeURIComponent(username)}/${encodeURIComponent(initialProfile.default_event_type_slug)}`,
    );
  }

  return <PublicProfile username={username} initialProfile={initialProfile} />;
}
