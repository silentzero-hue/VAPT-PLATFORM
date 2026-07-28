import { LayoutGrid, List } from "lucide-react";
import { cn } from "../../lib/cn";

export type ViewMode = "grid" | "list";

interface ViewToggleProps {
  value: ViewMode;
  onChange: (v: ViewMode) => void;
  className?: string;
  ariaLabel?: string;
}

export default function ViewToggle({
  value,
  onChange,
  className,
  ariaLabel = "View mode",
}: ViewToggleProps) {
  return (
    <div
      role="radiogroup"
      aria-label={ariaLabel}
      className={cn(
        "inline-flex items-center gap-0.5 p-0.5 rounded-lg",
        "bg-white/[0.04] border border-white/[0.08]",
        className
      )}
    >
      <ToggleButton
        active={value === "grid"}
        onClick={() => onChange("grid")}
        label="Grid view"
      >
        <LayoutGrid size={14} />
      </ToggleButton>
      <ToggleButton
        active={value === "list"}
        onClick={() => onChange("list")}
        label="List view"
      >
        <List size={14} />
      </ToggleButton>
    </div>
  );
}

function ToggleButton({
  active,
  onClick,
  children,
  label,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
  label: string;
}) {
  return (
    <button
      type="button"
      role="radio"
      aria-checked={active}
      aria-label={label}
      onClick={onClick}
      className={cn(
        "inline-flex items-center justify-center h-7 w-7 rounded-md",
        "transition-colors duration-200 ease-out",
        active
          ? "bg-accent/20 text-accent border border-accent/30"
          : "text-fg-muted hover:text-fg border border-transparent"
      )}
    >
      {children}
    </button>
  );
}
