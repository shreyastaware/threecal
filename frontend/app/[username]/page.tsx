import { PublicProfile } from "@/features/booking/components/public-profile";

export default async function PublicProfilePage({
  params,
}: {
  params: Promise<{ username: string }>;
}) {
  const { username } = await params;
  return <PublicProfile username={username} />;
}
