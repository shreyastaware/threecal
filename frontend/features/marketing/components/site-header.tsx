"use client";

import { AnimatePresence, motion, useScroll, useMotionValueEvent } from "framer-motion";
import { ArrowRight, Menu, Star, X as CloseIcon } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { GITHUB_URL } from "@/features/marketing/content";

const NAV_LINKS = [
  { label: "How it works", href: "#how-it-works" },
  { label: "Benefits", href: "#benefits" },
  { label: "Loved by", href: "#social-proof" },
  { label: "FAQ", href: "#faq" },
];

// Sticky, glassmorphic marketing nav. Gains a border + blur once the page
// scrolls past the hero, and collapses into a slide-down sheet on mobile.
export function SiteHeader() {
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);
  const { scrollY } = useScroll();

  useMotionValueEvent(scrollY, "change", (latest) => {
    setScrolled(latest > 24);
  });

  return (
    <header
      className={`site-header ${scrolled ? "site-header-scrolled" : ""}`}
    >
      <nav className="site-header-inner">
        <Link href="/" className="wordmark">
          threecal<span>.</span>
        </Link>

        <div className="site-header-links">
          {NAV_LINKS.map((link) => (
            <a key={link.href} href={link.href}>
              {link.label}
            </a>
          ))}
        </div>

        <div className="site-header-actions">
          <a
            href={GITHUB_URL}
            target="_blank"
            rel="noreferrer noopener"
            className="github-chip"
          >
            <Star size={13} strokeWidth={2.4} />
            Open source
          </a>
          <Link href="/login" className="nav-login">
            Sign in
          </Link>
          <Link href="/register" className="nav-cta">
            Start Free <ArrowRight size={15} />
          </Link>
        </div>

        <button
          type="button"
          className="site-header-toggle"
          aria-label={open ? "Close menu" : "Open menu"}
          aria-expanded={open}
          onClick={() => setOpen((current) => !current)}
        >
          {open ? <CloseIcon size={20} /> : <Menu size={20} />}
        </button>
      </nav>

      <AnimatePresence>
        {open ? (
          <motion.div
            className="site-header-sheet"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25, ease: "easeInOut" }}
          >
            <div className="site-header-sheet-inner">
              {NAV_LINKS.map((link) => (
                <a key={link.href} href={link.href} onClick={() => setOpen(false)}>
                  {link.label}
                </a>
              ))}
              <a href={GITHUB_URL} target="_blank" rel="noreferrer noopener">
                GitHub
              </a>
              <Link href="/login" onClick={() => setOpen(false)}>
                Sign in
              </Link>
              <Link href="/register" className="nav-cta" onClick={() => setOpen(false)}>
                Start Free <ArrowRight size={15} />
              </Link>
            </div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </header>
  );
}
