"use client";

import { InlineComment } from "@/components/ui/InlineComment";

type CommentHistoryProps = {
  items: string[];
};

export function CommentHistory({ items }: CommentHistoryProps) {
  return (
    <div className="text-sm">
      <p className="font-medium">Комментарии и история</p>
      <div className="mb-3">
        {items.map((item, i) => (
          <div key={i} className="p-2 rounded-lg">
            <span className="text-xs text-(--color-secondary)">{item}</span>
          </div>
        ))}
      </div>
      <InlineComment />
    </div>
  );
}