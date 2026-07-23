import { FAQ } from "@/features/marketing/content";

// Accordion-free FAQ using native <details> for zero-JS progressive disclosure.
export function Faq() {
  return (
    <section className="marketing-section" id="faq">
      <header className="marketing-section-head">
        <span className="kicker kicker-dark">FAQ</span>
        <h2>Questions, answered</h2>
      </header>
      <div className="faq-list">
        {FAQ.map((item) => (
          <details key={item.question} className="faq-item">
            <summary>
              {item.question}
              <span className="faq-mark" aria-hidden />
            </summary>
            <p>{item.answer}</p>
          </details>
        ))}
      </div>
    </section>
  );
}
