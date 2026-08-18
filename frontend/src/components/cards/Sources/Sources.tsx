"use client";

import { Button } from "@/components/ui/Button/button";
import { Icon } from "@/components/ui/Icon/Icon";

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
  return (
    <div className="space-y-2 text-sm">
      <p className="font-medium">Источники</p>
      <div className="space-y-2">
        {items.map((item, i) => (
          <Button
            key={i}
            className="w-full flex surface-block interactive-surface p-0"
            endIcon={<Icon name="link" />}
            variant="tertiary"
            size="none"
            justifyContent="space-between"
            onClick={() => window.open(source, "_blank", "noopener,noreferrer")}
          >
            <div className="flex flex-col items-baseline text-(--color-ink) forn-medium text-xs">
              <span className="text-(--color-ink)">{item.name}</span>
              <a
                href={source}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs text-(--color-secondary)"
              >
                {source}
              </a>
            </div>
          </Button>
        ))}
      </div>
    </div>
  );
}
