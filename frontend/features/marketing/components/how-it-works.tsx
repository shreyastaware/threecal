import { HOW_IT_WORKS } from "@/features/marketing/content";

// Three-step explainer: Create -> Share -> Get booked.
export function HowItWorks() {
  return (
    <section className="marketing-section" id="how-it-works">
      <header className="marketing-section-head">
        <span className="kicker kicker-dark">How it works</span>
        <h2>Create → Share → Get booked</h2>
      </header>
      <ol className="how-grid">
        {HOW_IT_WORKS.map((step) => (
          <li key={step.index} className="how-step">
            <span className="how-index">{step.index}</span>
            <h3>{step.title}</h3>
            <p>{step.description}</p>
          </li>
        ))}
      </ol>
    </section>
  );
}
