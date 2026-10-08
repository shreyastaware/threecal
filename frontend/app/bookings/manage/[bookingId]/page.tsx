import type { Metadata } from "next";

import { ManageBooking } from "@/features/bookings/components/manage-booking";

export const metadata: Metadata = {
  title: "Manage your booking · threecal",
  // Links carry a private token; keep them out of search results.
  robots: { index: false, follow: false },
  referrer: "no-referrer",
};

export default async function ManageBookingPage({
  params,
  searchParams,
}: {
  params: Promise<{ bookingId: string }>;
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}) {
  const { bookingId } = await params;
  const { token } = await searchParams;
  return <ManageBooking bookingId={bookingId} token={typeof token === "string" ? token : null} />;
}
