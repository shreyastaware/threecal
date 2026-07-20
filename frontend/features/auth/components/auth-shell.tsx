import Link from "next/link";

export function AuthShell({
  children,
  eyebrow,
  title,
  description,
}: {
  children: React.ReactNode;
  eyebrow: string;
  title: string;
  description: string;
}) {
  return (
    <main className="auth-canvas">
      <div className="auth-orbit auth-orbit-one" />
      <div className="auth-orbit auth-orbit-two" />
      <section className="auth-story" aria-label="Threecal introduction">
        <Link href="/" className="wordmark wordmark-light">
          threecal<span>.</span>
        </Link>
        <div className="auth-story-copy">
          <p className="kicker">Appointments, with intent</p>
          <h2>
            Make your time
            <br />
            <em>worth showing up for.</em>
          </h2>
          <p>
            One considered link for your calendar, expertise, and paid
            sessions.
          </p>
        </div>
        <div className="schedule-fragment" aria-hidden="true">
          <span>THU · 24</span>
          <strong>10:30</strong>
          <i />
          <small>Strategy call · 45 min</small>
        </div>
      </section>

      <section className="auth-panel">
        <div className="auth-form-wrap">
          <p className="kicker kicker-dark">{eyebrow}</p>
          <h1>{title}</h1>
          <p className="auth-description">{description}</p>
          {children}
        </div>
      </section>
    </main>
  );
}
