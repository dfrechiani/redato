import { cn } from "@/lib/cn";

interface Props {
  className?: string;
  size?: "sm" | "md" | "lg";
}

const sizes = {
  sm: { wrap: "text-base", dot: "h-2 w-2" },
  md: { wrap: "text-xl", dot: "h-2.5 w-2.5" },
  lg: { wrap: "text-3xl", dot: "h-3 w-3" },
};

/**
 * Wordmark: "Redato" em fonte display + dot lime indicando "Projeto ATO".
 */
export function Logo({ className, size = "md" }: Props) {
  const s = sizes[size];
  return (
    <span
      className={cn(
        "inline-flex items-baseline gap-1.5 font-display tracking-tight",
        s.wrap,
        className,
      )}
    >
      <span>Redato</span>
      <span
        className={cn("rounded-full bg-lime translate-y-[-1px]", s.dot)}
        aria-hidden="true"
      />
    </span>
  );
}
