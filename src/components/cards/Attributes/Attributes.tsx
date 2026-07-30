import Button from "@/components/ui/Button/button";
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
          <p className="text-xs text-[var(--color-muted)]">Конкурент / объект</p>
          <p className="text-xs text-[var(--color-ink)]">{incident.object}</p>
          <p className="text-xs text-[var(--color-muted)]">Категория</p>
          <p className="text-xs text-[var(--color-ink)]">{incident.category}</p>
          <p className="text-xs text-[var(--color-muted)]">Приоритет</p>
          <p>
            <span className="priority priority-accent text-xs">{incident.priority}</span>
          </p>
          <p className="text-xs text-[var(--color-muted)]">Тональность</p>
          <p>
            <span className="tonality tonality-positive text-xs">{incident.tonality}</span>
          </p>
          <p className="text-xs text-[var(--color-muted)]">Регион</p>
          <p className="text-xs text-[var(--color-ink)]">{incident.region}</p>
        </div>
        {(onConfirm || onFix) && (
          <div className="flex gap-2">
            {onConfirm && (
              <Button
                variant="secondary"
                onClick={onConfirm}
                style={{
                  backgroundColor: "var(--color-accent)",
                  color: "#fff",
                  borderColor: "transparent",
                }}
              >
                Подтвердить разметку
              </Button>
            )}
            {onFix && (
              <Button
                variant="secondary"
                onClick={onFix}
                style={{
                  backgroundColor: "#F2F3F7",
                  color: "var(--color-secondary)",
                  borderColor: "transparent",
                }}
              >
                Исправить
              </Button>
            )}
          </div>
        )}
      </div>
    </>
  );
}