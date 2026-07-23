import { TRUSTED_ROLES } from "@/features/marketing/content";

// Social proof strip listing the professions threecal serves.
export function TrustedBy() {
  return (
    <section className="trusted-by" aria-label="Trusted by">
      <span className="trusted-label">Trusted by</span>
      <ul className="trusted-roles">
        {TRUSTED_ROLES.map((role) => (
          <li key={role}>{role}</li>
        ))}
      </ul>
    </section>
  );
}
