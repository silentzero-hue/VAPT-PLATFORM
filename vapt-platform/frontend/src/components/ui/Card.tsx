import { type ReactNode, type MouseEvent, type KeyboardEvent } from "react";
import { cn } from "../../lib/cn";

interface CardProps {
  className?: string;
  children: ReactNode;
  selected?: boolean;
  onClick?: (e: MouseEvent<HTMLDivElement>) => void;
  role?: string;
  ariaLabel?: string;
}

export default function Card({
  className,
  children,
  selected = false,
  onClick,
  role,
  ariaLabel,
}: CardProps) {
  const interactive = !!onClick;
  const handleKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    if (!onClick) return;
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onClick(e as unknown as MouseEvent<HTMLDivElement>);
    }
  };
  return (
    <div
      className={cn(
        "relative rounded-2xl bg-white/[0.04] border border-white/[0.08] overflow-hidden",
        "shadow-[0_4px_24px_rgba(0,0,0,0.25)]",
        "transition-all duration-200 ease-out",
        interactive && "card-hover cursor-pointer",
        selected && "ring-2 ring-accent/50 bg-accent/10 border-accent/40",
        className
      )}
      onClick={onClick}
      onKeyDown={handleKeyDown}
      role={role ?? (interactive ? "button" : undefined)}
      aria-label={ariaLabel}
      aria-pressed={interactive ? selected : undefined}
      tabIndex={interactive ? 0 : undefined}
    >
      {children}
    </div>
  );
}
