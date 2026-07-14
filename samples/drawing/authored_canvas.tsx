// FIXTURE (block-hard): Claude hand-drawing on a <canvas> in an authored composition file.
// Expected: drawing_check exit 3 (canvas 2D drawing is never overridable).
import { useEffect, useRef } from "react";

export function HeroViz() {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const ctx = ref.current!.getContext("2d")!;
    ctx.beginPath();
    ctx.fillRect(0, 0, 400, 300);
    ctx.arc(200, 150, 80, 0, Math.PI * 2);
    ctx.fillText("growth", 20, 40);
  }, []);
  return <canvas ref={ref} width={400} height={300} />;
}
