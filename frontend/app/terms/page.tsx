import type { Metadata } from "next";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Terms & Conditions · threecal",
  description: "The terms that govern your use of threecal.",
};

export default function TermsPage() {
  return (
    <main className="legal-canvas">
      <Link href="/" className="wordmark">
        threecal<span>.</span>
      </Link>
      <h1>Terms &amp; Conditions</h1>
      <p className="legal-updated">Last updated: 23 July 2026</p>

      <p>
        These Terms &amp; Conditions (&ldquo;Terms&rdquo;) govern your access to
        and use of threecal.com and related services (&ldquo;threecal&rdquo;,
        &ldquo;we&rdquo;, &ldquo;us&rdquo;). By creating an account or booking an
        appointment, you agree to these Terms.
      </p>

      <h2>1. The service</h2>
      <p>
        threecal lets professionals publish a booking page, define appointment
        types and pricing, and accept prepaid bookings from their clients. We
        provide the platform; you are responsible for the services you deliver
        to your own clients.
      </p>

      <h2>2. Accounts</h2>
      <p>
        You must provide accurate information and keep your credentials secure.
        You are responsible for all activity under your account. Clients booking
        an appointment are not required to create an account.
      </p>

      <h2>3. Payments</h2>
      <p>
        Payments are processed through third-party payment providers. When a
        client books a prepaid appointment, funds are collected upfront through
        the connected provider. You are responsible for setting your prices,
        honouring bookings, and handling refunds in line with your own policies
        and applicable law.
      </p>

      <h2>4. Cancellations &amp; refunds</h2>
      <p>
        Cancellation and refund terms for individual appointments are set by the
        professional offering the service. threecal is not a party to that
        agreement and does not arbitrate disputes between professionals and
        their clients.
      </p>

      <h2>5. Acceptable use</h2>
      <ul>
        <li>Do not use threecal for unlawful, harmful, or fraudulent activity.</li>
        <li>Do not attempt to disrupt, reverse engineer, or overload the service.</li>
        <li>Do not misrepresent your identity or the services you offer.</li>
      </ul>

      <h2>6. Availability</h2>
      <p>
        We aim to keep threecal available and reliable but do not guarantee
        uninterrupted access. Features may change, and we may suspend accounts
        that violate these Terms.
      </p>

      <h2>7. Liability</h2>
      <p>
        To the fullest extent permitted by law, threecal is provided
        &ldquo;as is&rdquo; and we are not liable for indirect or consequential
        losses arising from your use of the service.
      </p>

      <h2>8. Changes</h2>
      <p>
        We may update these Terms from time to time. Material changes will be
        communicated, and continued use of threecal constitutes acceptance of
        the revised Terms.
      </p>

      <h2>9. Contact</h2>
      <p>
        Questions about these Terms can be sent to support@threecal.com.
      </p>

      <Link href="/" className="legal-back">
        <ArrowLeft size={15} /> Back to home
      </Link>
    </main>
  );
}
