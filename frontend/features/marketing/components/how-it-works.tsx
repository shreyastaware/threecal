import { Link2, Rocket, Send } from "lucide-react";

import { HOW_IT_WORKS } from "@/features/marketing/content";
import { Reveal, RevealGroup } from "@/features/marketing/components/reveal";

const STEP_ICONS = [Rocket, Send, Link2];

// Three-step explainer: Create -> Share -> Get booked, laid out as connected
// bento cards.
export function HowItWorks() {
  return (
    <section className="marketing-section" id="how-it-works">
      <Reveal className="marketing-section-head">
        <span className="kicker kicker-dark">How it works</span>
        <h2>Create → Share → Get booked</h2>
      </Reveal>

      <RevealGroup as="ol" className="how-grid" stagger={0.12}>
        {HOW_IT_WORKS.map((step, index) => {
          const Icon = STEP_ICONS[index] ?? Rocket;
          return (
            <Reveal as="li" key={step.index} className="how-step">
              <div className="how-step-icon">
                <Icon size={20} strokeWidth={1.6} />
              </div>
              <span className="how-index">{step.index}</span>
              <h3>{step.title}</h3>
              <p>{step.description}</p>
            </Reveal>
          );
        })}
      </RevealGroup>
    </section>
  );
}
