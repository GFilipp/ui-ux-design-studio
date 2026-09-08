// Fixture: a kibo-ui registry install (type registry:ui, files[].path "index.tsx") lands in the
// shadcn `aliases.ui` dir. Same illustration-scale svg as authored_illustration.tsx.
// Expected: drawing_check exit 0 — exempt via the ("components","ui") tuple, NOT a per-library entry.
export function KiboGantt() {
  return (
    <svg viewBox="0 0 800 400" xmlns="http://www.w3.org/2000/svg">
      <path d="M12 84c31-52 79-71 128-53 49 18 71 66 62 118-9 52-49 88-101 92-52 4-99-25-114-71-15-46 4-98 48-121 44-23 101-14 133 22 32 36 38 92 14 133-24 41-77 64-124 53-47-11-86-54-91-104-5-50 25-101 72-119 47-18 105-1 136 40" fill="none" stroke="#222" strokeWidth="3"/>
      <path d="M40 200c28-40 70-56 112-42 42 14 63 58 55 104-8 46-44 78-90 82-46 4-88-22-101-63" fill="none" stroke="#333" strokeWidth="2"/>
      <path d="M88 120c22-30 55-42 86-31 31 11 47 43 41 77-6 34-33 58-67 61" fill="none" stroke="#444" strokeWidth="2"/>
      <circle cx="400" cy="200" r="60" fill="none" stroke="#555" strokeWidth="2"/>
      <circle cx="470" cy="240" r="40" fill="none" stroke="#666" strokeWidth="2"/>
      <rect x="520" y="140" width="120" height="90" fill="none" stroke="#777" strokeWidth="2"/>
      <polygon points="660,300 700,240 740,300" fill="none" stroke="#888" strokeWidth="2"/>
      <ellipse cx="300" cy="330" rx="70" ry="30" fill="none" stroke="#999" strokeWidth="2"/>
      <path d="M150 340c40-20 90-20 130 0" fill="none" stroke="#aaa" strokeWidth="2"/>
    </svg>
  );
}
