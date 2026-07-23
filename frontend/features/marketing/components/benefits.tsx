import { BENEFITS } from "@/features/marketing/content";

// Grid of product benefits, each backed by a lucide icon.
export function Benefits() {
  return (
    <section className="marketing-section" id="benefits">
      <header className="marketing-section-head">
        <span className="kicker kicker-dark">Benefits</span>
        <h2>Everything you need to get paid for your time</h2>
      </header>
      <div className="benefit-grid">
        {BENEFITS.map(({ icon: Icon, title, description }) => (
          <article key={title} className="benefit-card">
            <Icon size={22} strokeWidth={1.5} />
            <h3>{title}</h3>
            <p>{description}</p>
          </article>
        ))}
      </div>
    </section>
  );
}
