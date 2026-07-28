import { type ReactNode } from "react";
import AppleIcon, { type AppleIconName } from "./AppleIcon";

interface EmptyStateProps {
  icon?: ReactNode;
  iconName?: AppleIconName;
  title: string;
  description?: string;
  cta?: ReactNode;
  className?: string;
}

export default function EmptyState({
  icon,
  iconName,
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
      {(icon || iconName) && (
        <div className="h-12 w-12 rounded-2xl glass flex items-center justify-center">
          {icon ?? <AppleIcon name={iconName!} size={20} className="text-fg-muted" />}
        </div>
      )}
      <div className="space-y-1 max-w-sm">
        <div className="text-sm font-medium text-fg">{title}</div>
        {description && (
          <div className="text-xs text-fg-muted leading-relaxed">{description}</div>
        )}
      </div>
      {cta && <div className="pt-1">{cta}</div>}
    </div>
  );
}
