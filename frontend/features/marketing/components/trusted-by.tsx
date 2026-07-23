"use client";

import { motion } from "framer-motion";

import { TRUSTED_ROLES } from "@/features/marketing/content";

// Infinite horizontal marquee of the professions threecal serves. Duplicated
// once so the looped translateX animation reads as seamless.
export function TrustedBy() {
  const roles = [...TRUSTED_ROLES, ...TRUSTED_ROLES];

  return (
    <section className="trusted-by" aria-label="Trusted by">
      <span className="trusted-label">Trusted by</span>
      <div className="trusted-marquee">
        <motion.ul
          className="trusted-track"
          animate={{ x: ["0%", "-50%"] }}
          transition={{ duration: 22, repeat: Infinity, ease: "linear" }}
        >
          {roles.map((role, index) => (
            <li key={`${role}-${index}`}>{role}</li>
          ))}
        </motion.ul>
      </div>
    </section>
  );
}
