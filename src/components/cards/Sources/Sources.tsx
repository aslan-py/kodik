"use client";

import { Button } from "@/components/ui/Button/button";
import { Icon } from "@/components/ui/Icon/Icon";
import { TagList } from "@/components/ui/TagList";

type SourceItem = {
  name: string;
  date: string;
  label: string;
};

type SourcesProps = {
  source: string;
  items: SourceItem[];
};

export function Sources({ source, items }: SourcesProps) {
  const tagItems = [`Основной источник: ${source}`, source];
  return (
    <div className="space-y-4 text-sm">
      <p className="font-medium">Источники</p>
      <TagList items={tagItems} />
      <div className="space-y-2">
        {items.map((item, i) => (
            // className="surface-block interactive-surface flex items-center justify-between rounded-lg"
            <Button
             key={i}
              className="w-full flex surface-block interactive-surface"
              endIcon={<Icon name="link" />}
              variant="tertiary"
              justifyContent="space-between"
            >
              <div className="flex flex-col items-baseline text-(--color-ink) forn-medium text-xs">
                <span className="text-(--color-ink)">{item.name}</span>
                <span className="text-xs text-(--color-secondary)">
                  {item.date} · {item.label}
                </span>
              </div>
            </Button>
        ))}
      </div>
    </div>
  );
}
