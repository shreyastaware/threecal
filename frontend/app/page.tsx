import { ArrowRight, Clock3 } from "lucide-react";
import Link from "next/link";

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
            Get your link <ArrowRight size={15} />
          </Link>
        </div>
      </nav>
      <section className="home-hero">
        <p className="kicker kicker-dark">Paid appointment booking</p>
        <h1>
          Your calendar,
          <br />
          <em>on your terms.</em>
        </h1>
        <p className="home-lede">
          A thoughtful booking space for people whose time and expertise carry
          real value.
        </p>
        <Link href="/register" className="hero-cta">
          Start with threecal <ArrowRight size={18} />
        </Link>
      </section>
      <aside className="home-ticket" aria-label="Example appointment">
        <div>
          <Clock3 size={18} />
          <span>Next opening</span>
        </div>
        <strong>Thursday, 10:30</strong>
        <small>45 minute advisory session</small>
      </aside>
      <p className="home-index">01 — MAKE TIME COUNT</p>
    </main>
  );
}
