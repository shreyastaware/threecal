export function StatusMessage({
  children,
  tone = "error",
}: {
  children: React.ReactNode;
  tone?: "error" | "success" | "notice";
}) {
  return <p className={`status-message status-${tone}`}>{children}</p>;
}
