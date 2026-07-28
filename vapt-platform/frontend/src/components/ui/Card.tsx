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
        "relative rounded-2xl bg-paper-strong border border-hairline overflow-hidden text-ink",
        "shadow-card",
        "transition-all duration-200 ease-out",
        interactive && "card-hover cursor-pointer",
        selected && "ring-2 ring-finder-blue/50 bg-finder-blue-soft border-finder-blue/40",
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
