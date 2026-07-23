import type { Metadata } from "next";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Privacy Policy · threecal",
  description: "How threecal collects, uses and protects your data.",
};

export default function PrivacyPage() {
  return (
    <main className="legal-canvas">
      <Link href="/" className="wordmark">
        threecal<span>.</span>
      </Link>
      <h1>Privacy Policy</h1>
      <p className="legal-updated">Last updated: 23 July 2026</p>

      <p>
        This Privacy Policy explains how threecal.com (&ldquo;threecal&rdquo;,
        &ldquo;we&rdquo;, &ldquo;us&rdquo;) collects, uses, and protects personal
        information when you use our service.
      </p>

      <h2>1. Information we collect</h2>
      <ul>
        <li>
          <strong>Account data:</strong> name, email, and profile details you
          provide when creating a booking page.
        </li>
        <li>
          <strong>Booking data:</strong> appointment details and the name,
          email, and notes provided by clients when they book.
        </li>
        <li>
          <strong>Payment data:</strong> handled by our payment providers; we
          store only limited transaction metadata, not full card details.
        </li>
        <li>
          <strong>Usage data:</strong> analytics and diagnostic information to
          improve and secure the service.
        </li>
      </ul>

      <h2>2. How we use information</h2>
      <p>
        We use your information to operate the booking platform, process
        prepaid appointments, sync calendars, send reminders and notifications,
        provide support, and improve threecal. We do not sell your personal
        information.
      </p>

      <h2>3. Third-party services</h2>
      <p>
        threecal integrates with providers for payments, calendar syncing,
        email delivery, analytics, and monitoring. These providers process data
        on our behalf under their own privacy commitments.
      </p>

      <h2>4. Calendars &amp; emails</h2>
      <p>
        With your permission, we access connected calendars to read and write
        availability and appointments. We send transactional emails such as
        booking confirmations and reminders to you and your clients.
      </p>

      <h2>5. Data retention</h2>
      <p>
        We retain personal information for as long as your account is active or
        as needed to provide the service and comply with legal obligations. You
        may request deletion of your account and associated data.
      </p>

      <h2>6. Security</h2>
      <p>
        We use reasonable technical and organisational measures to protect your
        data. No system is perfectly secure, but we work to safeguard the
        information entrusted to us.
      </p>

      <h2>7. Your rights</h2>
      <p>
        Depending on your location, you may have rights to access, correct,
        export, or delete your personal data. Contact us to exercise these
        rights.
      </p>

      <h2>8. Contact</h2>
      <p>
        For privacy questions or requests, email privacy@threecal.com.
      </p>

      <Link href="/" className="legal-back">
        <ArrowLeft size={15} /> Back to home
      </Link>
    </main>
  );
}
