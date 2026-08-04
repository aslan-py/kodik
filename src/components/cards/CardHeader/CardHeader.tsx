"use client";

import { Divider } from "@/components/ui/Divider";
import { statusClass, priorityClass } from "@/helpers/status";

export type CardHeaderProps = {
  priority: string;
  status: string;
  dateLabel: string;
  dateValue: string;
  title: string;
  tags: string[];
};

export function CardHeader({
  priority,
  status,
  dateLabel,
  dateValue,
  title,
  tags,
}: CardHeaderProps) {
  return (
    <div className="flex items-center justify-between w-full">
      <div className="flex flex-col">
        <p className="flex gap-2.5 mb-3.5 items-center">
          <span className={priorityClass(priority)}>{priority}</span>
          <span className={statusClass(status)}>{status}</span>
          <span className="text-xs text-(--color-muted)">
            {dateLabel} {dateValue}
          </span>
        </p>
        <h2 className="text-2xl font-semibold text-(--color-strong) mb-3.5 m-0">
          {title}
        </h2>
        <div className="text-xs text-(--color-muted)">
          {tags.map((tag, i) => (
            <span key={i}>
              {i > 0 && <span> · </span>}
              <span className={i === 0 ? "text-(--color-ink)" : ""}>{tag}</span>
            </span>
          ))}
        </div>
        <Divider />
      </div>
    </div>
  );
}