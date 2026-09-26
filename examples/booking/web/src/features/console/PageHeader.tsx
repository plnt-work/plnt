import type { ReactNode } from "react";

import { cn } from "@/lib/cn";

interface Props {
  title: string;
  description?: string;
  actions?: ReactNode;
  className?: string;
}

export default function PageHeader({ title, description, actions, className }: Props) {
  return (
    <div className={cn("flex items-start justify-between gap-4 mb-5", className)}>
      <div className="min-w-0">
        <h1 className="text-[20px] font-semibold text-coal-50 leading-tight">{title}</h1>
        {description && (
          <p className="mt-1 text-[12.5px] text-coal-200">{description}</p>
        )}
      </div>
      {actions && <div className="shrink-0 flex items-center gap-2">{actions}</div>}
    </div>
  );
}
