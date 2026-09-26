import { forwardRef, type ComponentPropsWithoutRef, type ElementRef } from "react";
import * as TabsPrimitive from "@radix-ui/react-tabs";

import { cn } from "@/lib/cn";

export const Tabs = TabsPrimitive.Root;

export const TabsList = forwardRef<
  ElementRef<typeof TabsPrimitive.List>,
  ComponentPropsWithoutRef<typeof TabsPrimitive.List>
>(({ className, ...props }, ref) => (
  <TabsPrimitive.List
    ref={ref}
    className={cn(
      "inline-flex items-center gap-1 border-b border-coal-500 px-0",
      className,
    )}
    {...props}
  />
));
TabsList.displayName = "TabsList";

export const TabsTrigger = forwardRef<
  ElementRef<typeof TabsPrimitive.Trigger>,
  ComponentPropsWithoutRef<typeof TabsPrimitive.Trigger>
>(({ className, ...props }, ref) => (
  <TabsPrimitive.Trigger
    ref={ref}
    className={cn(
      "relative inline-flex h-10 items-center gap-1.5 px-3 text-[13px] font-medium text-coal-200 outline-none transition-colors",
      "hover:text-coal-50",
      "data-[state=active]:text-iri-blue",
      "after:absolute after:left-2 after:right-2 after:-bottom-px after:h-[2px] after:bg-transparent",
      "data-[state=active]:after:bg-iri-blue",
      "focus-visible:ring-2 focus-visible:ring-iri-blue/40 focus-visible:ring-offset-2 focus-visible:ring-offset-coal-700",
      className,
    )}
    {...props}
  />
));
TabsTrigger.displayName = "TabsTrigger";

export const TabsContent = forwardRef<
  ElementRef<typeof TabsPrimitive.Content>,
  ComponentPropsWithoutRef<typeof TabsPrimitive.Content>
>(({ className, ...props }, ref) => (
  <TabsPrimitive.Content
    ref={ref}
    className={cn(
      "outline-none focus-visible:ring-2 focus-visible:ring-iri-blue/40 rounded-md",
      className,
    )}
    {...props}
  />
));
TabsContent.displayName = "TabsContent";
