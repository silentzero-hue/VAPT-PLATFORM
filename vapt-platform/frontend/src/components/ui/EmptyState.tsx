import { type ReactNode } from "react";

interface EmptyStateProps {
  icon?: ReactNode;
  title: string;
  description?: string;
  cta?: ReactNode;
  className?: string;
}

export default function EmptyState({
  icon,
  title,
  description,
  cta,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={
        "flex flex-col items-center justify-center text-center gap-3 py-12 px-6 " +
        (className ?? "")
      }
    >
      {icon && (
        <div className="h-12 w-12 rounded-2xl bg-paper-soft border border-hairline flex items-center justify-center">
          {icon}
        </div>
      )}
      <div className="space-y-1 max-w-sm">
        <div className="text-sm font-medium text-ink">{title}</div>
        {description && (
          <div className="text-xs text-ink-muted leading-relaxed">{description}</div>
        )}
      </div>
      {cta && <div className="pt-1">{cta}</div>}
    </div>
  );
}
