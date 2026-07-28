import { type ReactNode } from "react";
import { cn } from "../../lib/cn";

interface ToolbarProps {
  left?: ReactNode;
  right?: ReactNode;
  className?: string;
  children?: ReactNode;
}

export default function Toolbar({ left, right, className, children }: ToolbarProps) {
  return (
    <div
      className={cn(
        "sticky top-0 z-20 bg-paper-strong/80 backdrop-blur-xl",
        "border-b border-hairline",
        "px-6 py-3 flex items-center gap-3 text-ink",
        className
      )}
    >
      {left && <div className="flex items-center gap-3 min-w-0">{left}</div>}
      {children}
      {right && <div className="ml-auto flex items-center gap-2">{right}</div>}
    </div>
  );
}
