/** The mark: a hazard-profile bar with its baseline tick, the product's core idea. */
export function LogoMark({ className = "size-5" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden>
      <rect x="2" y="9" width="20" height="6" rx="1.5" className="fill-rule" />
      <rect x="2" y="9" width="13" height="6" rx="1.5" className="fill-cobalt" />
      <rect x="8.25" y="5" width="1.5" height="14" rx="0.75" className="fill-ink" />
    </svg>
  );
}
