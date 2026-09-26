import { forwardRef, type ButtonHTMLAttributes } from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/cn";

const buttonStyles = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap font-medium transition-colors " +
    "outline-none focus-visible:ring-2 focus-visible:ring-iri-blue/40 focus-visible:ring-offset-2 focus-visible:ring-offset-paper-100 " +
    "disabled:pointer-events-none disabled:opacity-40 select-none",
  {
    variants: {
      variant: {
        solid: "bg-ink-700 text-paper-100 hover:bg-ink-600",
        soft: "bg-paper-300 text-ink-700 hover:bg-paper-400",
        outline: "border border-paper-600 bg-transparent text-ink-700 hover:bg-paper-200",
        ghost: "text-ink-500 hover:bg-paper-300 hover:text-ink-700",
        danger: "bg-rust text-paper-100 hover:bg-rust/90",
        link: "text-iri-blue underline-offset-2 hover:underline",
      },
      size: {
        sm: "h-8 px-3 text-[13px] rounded-md",
        md: "h-10 px-4 text-sm rounded-md",
        lg: "h-11 px-5 text-base rounded-lg",
        icon: "h-9 w-9 rounded-md",
        pill: "h-8 px-3 text-[13px] rounded-pill",
      },
    },
    defaultVariants: { variant: "solid", size: "md" },
  },
);

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonStyles> {
  asChild?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        ref={ref}
        className={cn(buttonStyles({ variant, size }), className)}
        {...props}
      />
    );
  },
);
Button.displayName = "Button";

export { buttonStyles };
