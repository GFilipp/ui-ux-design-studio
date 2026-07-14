// FIXTURE (block-hard): canvas drawing via Path2D + ctx.fill(), no fillRect/beginPath.
// Codex flagged the original list missed Path2D/fill/stroke. Expected: drawing_check exit 3.
import { useEffect, useRef } from "react";

export function Sparkline() {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const ctx = ref.current!.getContext("2d")!;
    const p = new Path2D("M0 0 L120 40 L240 10");
    ctx.fill(p);
  }, []);
  return <canvas ref={ref} width={240} height={80} />;
}
