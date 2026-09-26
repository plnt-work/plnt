import type { ReactNode } from "react";
import { type LucideProps } from "lucide-react";

import { cn } from "@/lib/cn";

interface Props {
  icon?: React.ComponentType<LucideProps>;
  title: string;
  description?: string;
  action?: ReactNode;
  className?: string;
}

export function EmptyState({ icon: IconCmp, title, description, action, className }: Props) {
  return (
    <div className={cn("flex flex-col items-center justify-center text-center px-8 py-16 gap-3", className)}>
      {IconCmp && (
        <div className="size-10 rounded-full bg-coal-500/40 text-coal-100 grid place-items-center ring-1 ring-coal-400/60">
          <IconCmp className="size-5" />
        </div>
      )}
      <div>
        <h3 className="text-sm font-semibold text-coal-50">{title}</h3>
        {description && (
          <p className="mt-1 text-xs text-coal-200 max-w-[320px]">{description}</p>
        )}
      </div>
      {action && <div>{action}</div>}
    </div>
  );
}
