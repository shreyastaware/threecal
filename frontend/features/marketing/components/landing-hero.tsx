"use client";

import { motion } from "framer-motion";
import { ArrowRight, CalendarCheck2, Clock3, ShieldCheck, Sparkles } from "lucide-react";
import Link from "next/link";

const fadeUp = {
  hidden: { opacity: 0, y: 22 },
  visible: (delay: number) => ({
    opacity: 1,
    y: 0,
    transition: { duration: 0.65, delay, ease: [0.22, 1, 0.36, 1] as const },
  }),
};

// Above-the-fold hero: eyebrow badge, headline, primary CTA, and a floating
// booking-card mockup animated with framer-motion for a modern SaaS feel.
export function LandingHero() {
  return (
    <section className="hero-section">
      <div className="hero-glow" aria-hidden />
      <div className="hero-grid">
        <div className="hero-copy">
          <motion.div
            className="hero-badge"
            custom={0}
            initial="hidden"
            animate="visible"
            variants={fadeUp}
          >
            <Sparkles size={13} />
            Prepaid appointment booking, made simple
          </motion.div>

          <motion.h1
            custom={0.08}
            initial="hidden"
            animate="visible"
            variants={fadeUp}
          >
            Create your booking page
            <br />
            <em>and get paid before</em> the appointment.
          </motion.h1>

          <motion.p
            className="hero-lede"
            custom={0.16}
            initial="hidden"
            animate="visible"
            variants={fadeUp}
          >
            A thoughtful booking space for people whose time and expertise
            carry real value. Share one link, collect payment upfront, and
            let clients book themselves in.
          </motion.p>

          <motion.div
            className="hero-actions"
            custom={0.24}
            initial="hidden"
            animate="visible"
            variants={fadeUp}
          >
            <Link href="/register" className="hero-cta">
              Start Free <ArrowRight size={18} />
            </Link>
          </motion.div>

          <motion.p
            className="hero-note"
            custom={0.32}
            initial="hidden"
            animate="visible"
            variants={fadeUp}
          >
            No credit card required · Free while in beta
          </motion.p>
        </div>

        <motion.div
          className="hero-visual"
          initial={{ opacity: 0, y: 30, rotate: 2 }}
          animate={{ opacity: 1, y: 0, rotate: 0 }}
          transition={{ duration: 0.75, delay: 0.2, ease: [0.22, 1, 0.36, 1] }}
        >
          <motion.div
            className="hero-card"
            animate={{ y: [0, -10, 0] }}
            transition={{ duration: 6, repeat: Infinity, ease: "easeInOut" }}
          >
            <div className="hero-card-head">
              <Clock3 size={16} />
              <span>Next opening</span>
            </div>
            <strong>Thursday, 10:30</strong>
            <small>45 minute advisory session</small>
            <div className="hero-card-status">
              <ShieldCheck size={14} />
              Paid &amp; confirmed
            </div>
          </motion.div>

          <motion.div
            className="hero-card hero-card-float"
            animate={{ y: [0, 10, 0] }}
            transition={{ duration: 7, repeat: Infinity, ease: "easeInOut", delay: 0.5 }}
          >
            <div className="hero-card-head">
              <CalendarCheck2 size={16} />
              <span>This week</span>
            </div>
            <strong>12 bookings</strong>
            <small>100% prepaid, zero no-shows</small>
          </motion.div>
        </motion.div>
      </div>
    </section>
  );
}
