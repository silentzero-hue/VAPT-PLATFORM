import { ChevronLeft, ChevronRight } from "lucide-react";
import { cn } from "../../lib/cn";

interface NavArrowsProps {
  canGoBack: boolean;
  canGoForward: boolean;
  onBack: () => void;
  onForward: () => void;
  className?: string;
}

export default function NavArrows({
  canGoBack,
  canGoForward,
  onBack,
  onForward,
  className,
}: NavArrowsProps) {
  return (
    <div className={cn("flex items-center gap-0.5", className)}>
      <button
        type="button"
        aria-label="Go back"
        title="Back"
        onClick={onBack}
        disabled={!canGoBack}
        className={cn(
          "h-7 w-7 inline-flex items-center justify-center rounded-md",
          "text-fg-muted hover:text-fg hover:bg-white/[0.06]",
          "transition-colors duration-150 ease-out",
          "disabled:text-fg-subtle disabled:opacity-40 disabled:cursor-default disabled:hover:bg-transparent disabled:hover:text-fg-subtle"
        )}
      >
        <ChevronLeft size={15} />
      </button>
      <button
        type="button"
        aria-label="Go forward"
        title="Forward"
        onClick={onForward}
        disabled={!canGoForward}
        className={cn(
          "h-7 w-7 inline-flex items-center justify-center rounded-md",
          "text-fg-muted hover:text-fg hover:bg-white/[0.06]",
          "transition-colors duration-150 ease-out",
          "disabled:text-fg-subtle disabled:opacity-40 disabled:cursor-default disabled:hover:bg-transparent disabled:hover:text-fg-subtle"
        )}
      >
        <ChevronRight size={15} />
      </button>
    </div>
  );
}
