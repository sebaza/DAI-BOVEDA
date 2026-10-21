/** Brass lock plate with a keyhole in UCN tierra. Abstract; not the official crest. */
export function BovedaEmblema({ size = 40, className }: { size?: number; className?: string }) {
  return (
    <svg
      width={size}
      height={Math.round(size * 0.78)}
      viewBox="0 0 54 42"
      fill="none"
      aria-hidden="true"
      className={className}
    >
      <rect x="1.5" y="1.5" width="51" height="39" rx="9" fill="#c9a25e" stroke="#8e6e3a" strokeWidth="2" />
      <rect x="6" y="6" width="42" height="30" rx="6" fill="none" stroke="#8e6e3a" strokeOpacity="0.7" />
      <circle cx="9" cy="9" r="1.6" fill="#8e6e3a" />
      <circle cx="45" cy="9" r="1.6" fill="#8e6e3a" />
      <circle cx="9" cy="33" r="1.6" fill="#8e6e3a" />
      <circle cx="45" cy="33" r="1.6" fill="#8e6e3a" />
      <circle cx="27" cy="18" r="4.8" fill="#c06125" />
      <path d="M24.6 20.5h4.8l1.6 11h-8l1.6-11z" fill="#c06125" />
    </svg>
  );
}
