import { type MouseEvent, type ReactNode } from "react";
import { cn } from "../../lib/cn";

interface FolderCardProps {
  name: ReactNode;
  sub?: ReactNode;
  selected?: boolean;
  onClick?: (e: MouseEvent<HTMLButtonElement>) => void;
  onDoubleClick?: () => void;
  ariaLabel?: string;
  className?: string;
  iconSize?: "sm" | "md" | "lg";
  fromColor?: string;
  toColor?: string;
}

const SIZES: Record<NonNullable<FolderCardProps["iconSize"]>, { w: number; h: number }> = {
  sm: { w: 32, h: 24 },
  md: { w: 44, h: 34 },
  lg: { w: 56, h: 42 },
};

export default function FolderCard({
  name,
  sub,
  selected = false,
  onClick,
  onDoubleClick,
  ariaLabel,
  className,
  iconSize = "md",
  fromColor = "#6FB1FC",
  toColor = "#2E7CF6",
}: FolderCardProps) {
  const { w, h } = SIZES[iconSize];
  const gid = `fg-${fromColor.replace("#", "")}-${toColor.replace("#", "")}`;
  return (
    <button
      type="button"
      onClick={onClick}
      onDoubleClick={onDoubleClick}
      aria-label={ariaLabel}
      aria-pressed={selected}
      className={cn(
        "group flex flex-col items-center gap-1.5 p-2 rounded-lg",
        "border-2 border-transparent bg-transparent",
        "transition-colors duration-150 ease-out text-center",
        "focus:outline-none focus-visible:border-accent/40",
        "hover:bg-white/[0.04]",
        selected && "border-accent/60 bg-accent/10",
        className
      )}
    >
      <svg
        width={w}
        height={h}
        viewBox="0 0 44 34"
        className="drop-shadow-[0_2px_4px_rgba(46,124,246,0.18)]"
        aria-hidden="true"
      >
        <defs>
          <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor={fromColor} />
            <stop offset="1" stopColor={toColor} />
          </linearGradient>
        </defs>
        <path
          d="M2 6a2 2 0 0 1 2-2h10l3 4h21a2 2 0 0 1 2 2v20a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2z"
          fill={`url(#${gid})`}
        />
      </svg>
      <div className="text-[11.5px] leading-tight text-fg line-clamp-2 max-w-full">
        {name}
      </div>
      {sub && <div className="text-[10px] text-fg-subtle">{sub}</div>}
    </button>
  );
}
