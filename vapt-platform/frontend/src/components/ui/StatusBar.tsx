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
        "bg-paper-soft/85 backdrop-blur-md border-t border-hairline",
        "px-4 flex items-center justify-between text-[11px] text-ink-muted",
        className
      )}
    >
      <span>
        <span className="text-ink font-medium">{selectedCount}</span> selected
        <span className="mx-2 text-ink-subtle">·</span>
        <span className="text-ink font-medium">{totalCount}</span> total
      </span>
      {rightLabel && <span className="text-ink-muted">{rightLabel}</span>}
    </div>
  );
}
