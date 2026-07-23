import { ArrowRight, Clock3 } from "lucide-react";
import Link from "next/link";

// Above-the-fold hero with the primary conversion CTA.
export function LandingHero() {
  return (
    <section className="home-hero">
      <p className="kicker kicker-dark">Prepaid appointment booking</p>
      <h1>
        <em>Create your booking page</em>
        <br />
        and accept prepaid appointments.
      </h1>
      <p className="home-lede">
        A thoughtful booking space for people whose time and expertise carry
        real value. Share one link, get paid before the work begins.
      </p>
      <Link href="/register" className="hero-cta">
        Start Free <ArrowRight size={18} />
      </Link>

      <aside className="home-ticket" aria-label="Example appointment">
        <div>
          <Clock3 size={18} />
          <span>Next opening</span>
        </div>
        <strong>Thursday, 10:30</strong>
        <small>45 minute advisory session · prepaid</small>
      </aside>
    </section>
  );
}
