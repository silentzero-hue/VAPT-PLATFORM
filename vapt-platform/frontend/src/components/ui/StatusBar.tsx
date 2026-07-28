import { cn } from "../../lib/cn";

interface StatusBarProps {
  selectedCount: number;
  totalCount: number;
  className?: string;
  rightLabel?: string;
}

export default function StatusBar({
  selectedCount,
  totalCount,
  className,
  rightLabel,
}: StatusBarProps) {
  return (
    <div
      className={cn(
        "fixed bottom-0 left-0 right-0 z-30 h-6",
        "glass border-t border-white/[0.08]",
        "px-4 flex items-center justify-between text-[11px] text-fg-muted",
        className
      )}
    >
      <span>
        <span className="text-fg font-medium">{selectedCount}</span> selected
        <span className="mx-2 text-fg-subtle">·</span>
        <span className="text-fg font-medium">{totalCount}</span> total
      </span>
      {rightLabel && <span className="text-fg-muted">{rightLabel}</span>}
    </div>
  );
}
