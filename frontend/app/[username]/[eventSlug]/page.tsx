import { PublicBooking } from "@/features/booking/components/public-booking";

export default async function BookingPage({ params }: { params: Promise<{ username: string; eventSlug: string }> }) {
  const { username, eventSlug } = await params;
  return <PublicBooking username={username} eventSlug={eventSlug}/>;
}
