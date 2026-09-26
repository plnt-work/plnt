/**
 * Icon — typed re-export of lucide-react so the rest of the app imports from
 * one place. This lets us swap icon libraries (or add an internal icon set)
 * without grep-replacing every callsite.
 *
 * Usage:
 *   import { Icon } from "@/components/ui/Icon";
 *   <Icon name="send" className="size-4" />
 *
 * Or for ad-hoc icons not in the registry, import directly from lucide-react.
 */
import {
  ArrowRight,
  Check,
  Compass,
  Loader2,
  MapPin,
  Plus,
  Send,
  Sparkles,
  Trash2,
  X,
  type LucideProps,
} from "lucide-react";
import { forwardRef } from "react";

import { cn } from "@/lib/cn";

const REGISTRY = {
  "arrow-right": ArrowRight,
  check: Check,
  compass: Compass,
  loader: Loader2,
  "map-pin": MapPin,
  plus: Plus,
  send: Send,
  sparkles: Sparkles,
  trash: Trash2,
  x: X,
} as const;

export type IconName = keyof typeof REGISTRY;

interface Props extends LucideProps {
  name: IconName;
}

export const Icon = forwardRef<SVGSVGElement, Props>(({ name, className, ...props }, ref) => {
  const C = REGISTRY[name];
  return <C ref={ref} className={cn("size-4", className)} {...props} />;
});
Icon.displayName = "Icon";
