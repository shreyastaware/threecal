import { BOOKING_STATS, TESTIMONIALS } from "@/features/marketing/content";

// Testimonials paired with headline booking stats for credibility.
export function SocialProof() {
  return (
    <section className="marketing-section marketing-section-dark" id="social-proof">
      <header className="marketing-section-head">
        <span className="kicker">Social proof</span>
        <h2>Professionals who protect their time</h2>
      </header>
      <div className="social-grid">
        <ul className="testimonial-list">
          {TESTIMONIALS.map((item) => (
            <li key={item.name} className="testimonial-card">
              <blockquote>“{item.quote}”</blockquote>
              <p>
                <strong>{item.name}</strong>
                <span>{item.role}</span>
              </p>
            </li>
          ))}
        </ul>
        <ul className="stat-list">
          {BOOKING_STATS.map((stat) => (
            <li key={stat.label} className="stat-card">
              <strong>{stat.value}</strong>
              <span>{stat.label}</span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
