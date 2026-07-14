// FIXTURE (clean): a small inline icon in an authored file. Icons are legitimate and must
// NOT flag (<=4 shapes AND small d, or viewBox <=32). Expected: drawing_check exit 0.
export function CheckIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
      <path d="M20 6 L9 17 L4 12" />
    </svg>
  );
}
