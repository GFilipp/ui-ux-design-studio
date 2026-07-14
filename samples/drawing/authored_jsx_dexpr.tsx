// FIXTURE (block-soft): illustration whose path data is a JSX expression d={var}, which the
// naive `d="..."` regex could not measure, letting a big-viewBox illustration masquerade as an
// icon. Now unmeasurable d-expressions outside a tiny viewBox classify as illustration.
// Expected: drawing_check exit 2.
export function HeroArt({ a, b }: { a: string; b: string }) {
  return (
    <svg viewBox="0 0 800 600" xmlns="http://www.w3.org/2000/svg">
      <path d={a} />
      <path d={b} />
    </svg>
  );
}
