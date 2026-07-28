import { Columns, LayoutGrid, List } from "lucide-react";
import { cn } from "../../lib/cn";

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
        "bg-white/[0.04] border border-white/[0.08]",
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
          ? "bg-accent/20 text-accent border border-accent/30"
          : "text-fg-muted hover:text-fg border border-transparent"
      )}
    >
      {children}
    </button>
  );
}
