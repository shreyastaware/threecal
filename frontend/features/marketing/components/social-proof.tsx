import { BOOKING_STATS, TESTIMONIALS } from "@/features/marketing/content";
import { Reveal, RevealGroup } from "@/features/marketing/components/reveal";

// Testimonials paired with headline booking stats on a dark contrast panel.
export function SocialProof() {
  return (
    <section className="marketing-section marketing-section-dark" id="social-proof">
      <Reveal className="marketing-section-head">
        <span className="kicker">Social proof</span>
        <h2>Professionals who protect their time</h2>
      </Reveal>

      <div className="social-grid">
        <RevealGroup as="ul" className="testimonial-list" stagger={0.12}>
          {TESTIMONIALS.map((item) => (
            <Reveal as="li" key={item.name} className="testimonial-card">
              <blockquote>&ldquo;{item.quote}&rdquo;</blockquote>
              <p>
                <strong>{item.name}</strong>
                <span>{item.role}</span>
              </p>
            </Reveal>
          ))}
        </RevealGroup>

        <RevealGroup as="ul" className="stat-list" stagger={0.1}>
          {BOOKING_STATS.map((stat) => (
            <Reveal as="li" key={stat.label} className="stat-card">
              <strong>{stat.value}</strong>
              <span>{stat.label}</span>
            </Reveal>
          ))}
        </RevealGroup>
      </div>
    </section>
  );
}
