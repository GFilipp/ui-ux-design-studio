// FIXTURE (exempt): the SAME illustration-scale svg as authored_illustration.tsx, but living
// under components/aceternity/ — a vendored library file. Expected: drawing_check exit 0
// (provenance allowlist skips it; sanctioned copy-paste effects are byte-identical to art).
export function BackgroundBeams() {
  return (
    <svg viewBox="0 0 800 600" xmlns="http://www.w3.org/2000/svg" className="w-full">
      <path d="M10 10 C 120 200, 240 40, 360 180 S 520 300, 640 120 T 780 240 L 780 590 L 10 590 Z M40 80 q60 120 120 0 t120 0 t120 0 t120 0" />
      <path d="M20 300 c40 -80 120 -80 160 0 s120 80 160 0 s120 -80 160 0 s120 80 160 0 l0 120 l-640 0 z" />
      <path d="M0 0 L80 80 L160 0 L240 80 L320 0 L400 80 L480 0 L560 80 L640 0 L720 80 L800 0" />
      <circle cx="120" cy="120" r="40" />
      <circle cx="360" cy="200" r="30" />
      <rect x="500" y="300" width="120" height="80" />
      <polygon points="640,400 700,500 580,500" />
      <polyline points="10,10 40,80 90,20 140,120 190,40" />
      <ellipse cx="700" cy="120" rx="60" ry="30" />
      <line x1="0" y1="0" x2="800" y2="600" />
    </svg>
  );
}
