import { FAQ } from "@/features/marketing/content";
import { Reveal } from "@/features/marketing/components/reveal";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";

// FAQ powered by shadcn's Accordion (built on Base UI) for accessible,
// animated open/close panels.
export function Faq() {
  return (
    <section className="marketing-section" id="faq">
      <Reveal className="marketing-section-head">
        <span className="kicker kicker-dark">FAQ</span>
        <h2>Questions, answered</h2>
      </Reveal>

      <Reveal delay={0.1} className="faq-wrap">
        <Accordion className="faq-list">
          {FAQ.map((item) => (
            <AccordionItem key={item.question} value={item.question} className="faq-item">
              <AccordionTrigger className="faq-trigger">
                {item.question}
              </AccordionTrigger>
              <AccordionContent className="faq-content">
                <p>{item.answer}</p>
              </AccordionContent>
            </AccordionItem>
          ))}
        </Accordion>
      </Reveal>
    </section>
  );
}
