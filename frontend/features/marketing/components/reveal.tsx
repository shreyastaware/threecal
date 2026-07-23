"use client";

import { motion, type Variants } from "framer-motion";
import type { ReactNode } from "react";

// Shared scroll-triggered fade/rise animation used across marketing sections.
export function Reveal({
  children,
  delay = 0,
  y = 24,
  className,
  as = "div",
}: {
  children: ReactNode;
  delay?: number;
  y?: number;
  className?: string;
  as?: "div" | "li";
}) {
  const variants: Variants = {
    hidden: { opacity: 0, y },
    visible: {
      opacity: 1,
      y: 0,
      transition: { duration: 0.6, delay, ease: [0.22, 1, 0.36, 1] },
    },
  };

  const MotionTag = as === "li" ? motion.li : motion.div;

  return (
    <MotionTag
      className={className}
      initial="hidden"
      whileInView="visible"
      viewport={{ once: true, margin: "-80px" }}
      variants={variants}
    >
      {children}
    </MotionTag>
  );
}

// Wraps a list of children and staggers their entrance via context-free delay math.
export function RevealGroup({
  children,
  className,
  stagger = 0.08,
  as = "div",
}: {
  children: ReactNode[];
  className?: string;
  stagger?: number;
  as?: "div" | "ul" | "ol";
}) {
  const containerVariants: Variants = {
    hidden: {},
    visible: {
      transition: { staggerChildren: stagger },
    },
  };

  const MotionTag =
    as === "ul" ? motion.ul : as === "ol" ? motion.ol : motion.div;

  return (
    <MotionTag
      className={className}
      initial="hidden"
      whileInView="visible"
      viewport={{ once: true, margin: "-80px" }}
      variants={containerVariants}
    >
      {children}
    </MotionTag>
  );
}
