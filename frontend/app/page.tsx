import { ArrowRight } from "lucide-react";
import Link from "next/link";

import { Benefits } from "@/features/marketing/components/benefits";
import { Faq } from "@/features/marketing/components/faq";
import { HowItWorks } from "@/features/marketing/components/how-it-works";
import { LandingHero } from "@/features/marketing/components/landing-hero";
import { SiteFooter } from "@/features/marketing/components/site-footer";
import { SocialProof } from "@/features/marketing/components/social-proof";
import { TrustedBy } from "@/features/marketing/components/trusted-by";

export default function Home() {
  return (
    <main className="home-canvas">
      <nav className="home-nav">
        <Link href="/" className="wordmark">
          threecal<span>.</span>
        </Link>
        <div>
          <Link href="/login" className="nav-login">
            Sign in
          </Link>
          <Link href="/register" className="nav-cta">
            Start Free <ArrowRight size={15} />
          </Link>
        </div>
      </nav>

      <LandingHero />
      <TrustedBy />
      <HowItWorks />
      <Benefits />
      <SocialProof />
      <Faq />
      <SiteFooter />
    </main>
  );
}
