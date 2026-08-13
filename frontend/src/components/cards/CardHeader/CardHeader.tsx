"use client";

import { Divider } from "@/components/ui/Divider";
import { tonalityClass, priorityClass } from "@/helpers/status";
import { ReactNode } from "react";

export type CardHeaderProps = {
  priority: string;
  tonality: string;
  dateLabel: string;
  dateValue: string;
  title: string;
  tags: ReactNode[];
};

export function CardHeader({
  priority,
  tonality,
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
          {tonality ? <span className={tonalityClass(tonality)}>{tonality}</span> : null}
          <span className="text-xs text-(--color-muted)">
            {dateLabel} {dateValue}
          </span>
        </p>
        <h2 className="text-2xl font-semibold text-(--color-strong) mb-3.5 m-0">
          {title}
        </h2>
        <div className="text-xs">
          {tags.map((tag, i) => (
            <span key={i}>
              {i > 0 && <span> · </span>}
              <span className={"text-(--color-muted)"}>{tag}</span>
            </span>
          ))}
        </div>
        <Divider />
      </div>
    </div>
  );
}