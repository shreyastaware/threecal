import { Benefits } from "@/features/marketing/components/benefits";
import { Faq } from "@/features/marketing/components/faq";
import { HowItWorks } from "@/features/marketing/components/how-it-works";
import { LandingHero } from "@/features/marketing/components/landing-hero";
import { SiteFooter } from "@/features/marketing/components/site-footer";
import { SiteHeader } from "@/features/marketing/components/site-header";
import { SocialProof } from "@/features/marketing/components/social-proof";
import { TrustedBy } from "@/features/marketing/components/trusted-by";

export default function Home() {
  return (
    <main className="home-canvas">
      <SiteHeader />
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
