import { ArrowRight } from "lucide-react";
import Link from "next/link";

import { SOCIAL_LINKS } from "@/features/marketing/content";
import {
  InstagramIcon,
  RedditIcon,
  XIcon,
} from "@/features/marketing/components/social-icons";
import { Reveal } from "@/features/marketing/components/reveal";

const ICONS = {
  instagram: InstagramIcon,
  x: XIcon,
  reddit: RedditIcon,
};

// Closing CTA plus socials and legal links for the marketing site.
export function SiteFooter() {
  return (
    <footer className="site-footer">
      <Reveal className="footer-cta">
        <h2>
          Turn your time into <em>a link that pays.</em>
        </h2>
        <div className="footer-cta-actions">
          <Link href="/register" className="hero-cta">
            <div className="text-black flex"><span>Start Free </span> <ArrowRight size={18} /></div>
          </Link>
        </div>
      </Reveal>

      <div className="footer-meta">
        <Link href="/" className="wordmark wordmark-light">
          threecal<span>.</span>
        </Link>

        <ul className="footer-socials" aria-label="Social links">
          {SOCIAL_LINKS.map((social) => {
            const Icon = ICONS[social.icon];
            return (
              <li key={social.name}>
                <a
                  href={social.href}
                  target="_blank"
                  rel="noreferrer noopener"
                  aria-label={social.name}
                >
                  <Icon width={16} height={16} />
                </a>
              </li>
            );
          })}
        </ul>

        <nav className="footer-links" aria-label="Footer">
          <Link href="/terms">Terms &amp; Conditions</Link>
          <Link href="/privacy">Privacy Policy</Link>
          <Link href="/login">Sign in</Link>
        </nav>
      </div>

      <p className="footer-copy">© {new Date().getFullYear()} threecal.</p>
    </footer>
  );
}
