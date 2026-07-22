import type { ReactNode } from "react";

export function DashboardHeader({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow: string;
  title: ReactNode;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <header className="workspace-header">
      <div>
        <p className="kicker kicker-dark">{eyebrow}</p>
        <h1>{title}</h1>
        {description && <p className="workspace-header-description">{description}</p>}
      </div>
      {action}
    </header>
  );
}
