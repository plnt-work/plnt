/**
 * Drawer — right-side dialog primitive built on @radix-ui/react-dialog.
 *
 * Used for row-click detail panels in the new /console (Vertex AI shape):
 * the table stays mounted, the drawer slides over the right edge with
 * scoped content + close button + footer-action slot.
 */
import {
  forwardRef,
  type ComponentPropsWithoutRef,
  type ElementRef,
  type ReactNode,
} from "react";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { X } from "lucide-react";

import { cn } from "@/lib/cn";

export const Drawer = DialogPrimitive.Root;
export const DrawerTrigger = DialogPrimitive.Trigger;
export const DrawerClose = DialogPrimitive.Close;
export const DrawerPortal = DialogPrimitive.Portal;

export const DrawerOverlay = forwardRef<
  ElementRef<typeof DialogPrimitive.Overlay>,
  ComponentPropsWithoutRef<typeof DialogPrimitive.Overlay>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Overlay
    ref={ref}
    className={cn(
      "fixed inset-0 z-50 bg-coal-800/55 backdrop-blur-[2px]",
      "data-[state=open]:animate-in data-[state=open]:fade-in-0",
      "data-[state=closed]:animate-out data-[state=closed]:fade-out-0",
      className,
    )}
    {...props}
  />
));
DrawerOverlay.displayName = "DrawerOverlay";

interface ContentProps extends ComponentPropsWithoutRef<typeof DialogPrimitive.Content> {
  size?: "md" | "lg" | "xl";
}

const SIZE_CLASS: Record<NonNullable<ContentProps["size"]>, string> = {
  md: "w-[420px]",
  lg: "w-[560px]",
  xl: "w-[720px]",
};

export const DrawerContent = forwardRef<
  ElementRef<typeof DialogPrimitive.Content>,
  ContentProps
>(({ className, children, size = "md", ...props }, ref) => (
  <DrawerPortal>
    <DrawerOverlay />
    <DialogPrimitive.Content
      ref={ref}
      className={cn(
        "fixed top-0 right-0 bottom-0 z-50 flex flex-col",
        "bg-coal-700 border-l border-coal-500 text-coal-50 shadow-lg outline-none",
        SIZE_CLASS[size],
        "data-[state=open]:animate-in data-[state=open]:slide-in-from-right-4",
        "data-[state=closed]:animate-out data-[state=closed]:slide-out-to-right-4",
        className,
      )}
      {...props}
    >
      {children}
    </DialogPrimitive.Content>
  </DrawerPortal>
));
DrawerContent.displayName = "DrawerContent";

export function DrawerHeader({
  title,
  subtitle,
  badge,
  className,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  badge?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex items-start justify-between gap-3 px-5 py-4 border-b border-coal-500", className)}>
      <div className="min-w-0">
        <DialogPrimitive.Title className="text-base font-semibold text-coal-50 truncate">
          {title}
        </DialogPrimitive.Title>
        {subtitle && (
          <DialogPrimitive.Description className="mt-0.5 text-[12px] text-coal-200 truncate">
            {subtitle}
          </DialogPrimitive.Description>
        )}
        {badge && <div className="mt-2">{badge}</div>}
      </div>
      <DrawerClose
        className="rounded-md p-1 text-coal-200 hover:text-coal-50 hover:bg-coal-500/60 outline-none focus-visible:ring-2 focus-visible:ring-iri-blue/40"
        aria-label="Close"
      >
        <X className="size-4" />
      </DrawerClose>
    </div>
  );
}

export function DrawerBody({ className, ...props }: { className?: string; children?: ReactNode }) {
  return <div className={cn("flex-1 min-h-0 overflow-y-auto p-5", className)} {...props} />;
}

export function DrawerFooter({ className, ...props }: { className?: string; children?: ReactNode }) {
  return (
    <div
      className={cn(
        "flex items-center justify-end gap-2 px-5 py-3 border-t border-coal-500 bg-coal-700/60",
        className,
      )}
      {...props}
    />
  );
}
