import { Button } from "@/components/ui/Button/button";

export function RelatedTask() {
  return (
    <div className="space-y-4 text-sm">
      <p className="font-medium">Связанная задача</p>
      <p className="text-(--color-secondary)">
        Задача создана и связана с событием.
      </p>
      <Button
        variant="secondary"
        fullWidth
        className="flex flex-col items-start gap-1 p-4 h-auto text-left"
      >
        <span className="text-sm font-medium">
          Оценить влияние экспресс-доставки Wildberries
        </span>
        <span className="text-xs text-(--color-secondary) font-normal">
          Коммерческий отдел · сегодня 18:00 · В работе
        </span>
      </Button>
    </div>
  );
}