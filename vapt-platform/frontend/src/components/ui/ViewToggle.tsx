import { cn } from "../../lib/cn";
import { List, Columns, LayoutGrid } from "lucide-react";

export type ViewMode = "grid" | "list" | "column";

interface ViewToggleProps {
  value: ViewMode;
  onChange: (v: ViewMode) => void;
  className?: string;
  ariaLabel?: string;
  modes?: ViewMode[];
}

export default function ViewToggle({
  value,
  onChange,
  className,
  ariaLabel = "View mode",
  modes = ["grid", "list", "column"],
}: ViewToggleProps) {
  return (
    <div
      role="radiogroup"
      aria-label={ariaLabel}
      className={cn(
        "inline-flex items-center gap-0.5 p-0.5 rounded-lg",
        "bg-paper-soft border border-hairline",
        className
      )}
    >
      {modes.includes("grid") && (
        <ToggleButton
          active={value === "grid"}
          onClick={() => onChange("grid")}
          label="Grid view"
        >
          <LayoutGrid size={14} />
        </ToggleButton>
      )}
      {modes.includes("list") && (
        <ToggleButton
          active={value === "list"}
          onClick={() => onChange("list")}
          label="List view"
        >
          <List size={14} />
        </ToggleButton>
      )}
      {modes.includes("column") && (
        <ToggleButton
          active={value === "column"}
          onClick={() => onChange("column")}
          label="Column view"
        >
          <Columns size={14} />
        </ToggleButton>
      )}
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
          ? "bg-finder-blue/15 text-finder-blue border border-finder-blue/30"
          : "text-ink-muted hover:text-ink border border-transparent"
      )}
    >
      {children}
    </button>
  );
}
