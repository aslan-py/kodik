import { Button } from "@/components/ui/Button/button";
import type { IncidentItem } from "@/types/types";

type AttributesProps = {
  incident: IncidentItem;
  onConfirm?: () => void;
  onFix?: () => void;
};

export function Attributes({ incident, onConfirm, onFix }: AttributesProps) {
  return (
    <>
      <div className="space-y-4 text-sm">
        <p className="font-medium">Атрибуты</p>
        <div className="grid grid-cols-[160px_1fr] gap-x-4 gap-y-3">
          <p className="text-xs text-(--color-muted)">Конкурент / объект</p>
          <p className="text-xs text-(--color-ink)">{incident.object}</p>
          <p className="text-xs text-(--color-muted)">Категория</p>
          <p className="text-xs text-(--color-ink)">{incident.category}</p>
          <p className="text-xs text-(--color-muted)">Приоритет</p>
          <p>
            <span className="priority priority-accent text-xs">
              {incident.priority}
            </span>
          </p>
          <p className="text-xs text-(--color-muted)">Тональность</p>
          <p>
            <span className="tonality tonality-positive text-xs">
              {incident.tonality}
            </span>
          </p>
          <p className="text-xs text-(--color-muted)">Регион</p>
          <p className="text-xs text-(--color-ink)">{incident.region}</p>
        </div>
        {(onFix) && (
          <div className="flex gap-2">
            {onFix && (
              <Button variant="badge" badgeColor="secondary" className="font-semibold" onClick={onFix}>
                Исправить
              </Button>
            )}
          </div>
        )}
      </div>
    </>
  );
}
