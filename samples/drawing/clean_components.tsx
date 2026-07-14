// FIXTURE (clean): the sanctioned path — compose real library components, no raw svg/canvas.
// Expected: drawing_check exit 0.
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { BackgroundBeams } from "@/components/aceternity/background-beams";
import { Marquee } from "@/components/magicui/marquee";
import { ArrowRight } from "lucide-react";

export function Hero() {
  return (
    <section className="relative">
      <BackgroundBeams />
      <Card>
        <CardHeader>Less drag. More lift.</CardHeader>
        <CardContent>
          <p>Spot the bottleneck, focus the next sprint, show progress in 90 days.</p>
          <Button>
            Start <ArrowRight className="ml-2 size-4" />
          </Button>
        </CardContent>
      </Card>
      <Marquee>partners</Marquee>
    </section>
  );
}
