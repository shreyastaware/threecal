"use client";

import { motion } from "framer-motion";

import { BENEFITS } from "@/features/marketing/content";
import { Reveal, RevealGroup } from "@/features/marketing/components/reveal";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

// Bento-style grid of product benefits with a subtle hover lift.
export function Benefits() {
  return (
    <section className="marketing-section" id="benefits">
      <Reveal className="marketing-section-head">
        <span className="kicker kicker-dark">Benefits</span>
        <h2>Everything you need to get paid for your time</h2>
      </Reveal>

      <RevealGroup className="benefit-grid" stagger={0.08}>
        {BENEFITS.map(({ icon: Icon, title, description }, index) => (
          <Reveal key={title} className={index === 0 ? "benefit-card-lg" : undefined}>
            <motion.div whileHover={{ y: -6 }} transition={{ duration: 0.25 }} className="h-full">
              <Card className="benefit-card">
                <CardHeader>
                  <div className="benefit-icon">
                    <Icon size={20} strokeWidth={1.6} />
                  </div>
                  <CardTitle className="benefit-title">{title}</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="benefit-desc">{description}</p>
                </CardContent>
              </Card>
            </motion.div>
          </Reveal>
        ))}
      </RevealGroup>
    </section>
  );
}
