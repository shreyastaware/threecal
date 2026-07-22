"use client";

import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useState } from "react";

const roles = ["Advisors", "Coaches", "Consultants", "Doctors"];

export function RoleTicker() {
  const [index, setIndex] = useState(0);

  useEffect(() => {
    const timer = window.setInterval(() => setIndex((current) => (current + 1) % roles.length), 2600);
    return () => window.clearInterval(timer);
  }, []);

  return (
    <span className="role-ticker" aria-live="polite">
      <AnimatePresence mode="wait">
        <motion.em key={roles[index]} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -20 }} transition={{ duration: .35 }}>
          {roles[index]}
        </motion.em>
      </AnimatePresence>
    </span>
  );
}
