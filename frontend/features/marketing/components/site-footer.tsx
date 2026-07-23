import { ArrowRight } from "lucide-react";
import Link from "next/link";

// Closing CTA plus legal + navigation links for the marketing site.
export function SiteFooter() {
  return (
    <footer className="site-footer">
      <div className="footer-cta">
        <h2>
          Turn your time into <em>a link that pays.</em>
        </h2>
        <Link href="/register" className="hero-cta">
          Start Free <ArrowRight size={18} />
        </Link>
      </div>
      <div className="footer-meta">
        <Link href="/" className="wordmark wordmark-light">
          threecal<span>.</span>
        </Link>
        <nav className="footer-links" aria-label="Footer">
          <Link href="/terms">Terms &amp; Conditions</Link>
          <Link href="/privacy">Privacy Policy</Link>
          <Link href="/login">Sign in</Link>
        </nav>
        <p className="footer-copy">
          © {new Date().getFullYear()} threecal. All rights reserved.
        </p>
      </div>
    </footer>
  );
}
