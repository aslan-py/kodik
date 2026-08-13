// @/components/tables/columns/triggerColumns.tsx
import { TableColumn } from "@/components/ui/Table/Table";
import { Trigger } from "@/api/monitoringApi";

const STATUS_OPTIONS = [
  { label: "Активный", value: "1" },
  { label: "Приостановлен", value: "0" },
];

export function useTriggerColumns(): TableColumn<Trigger>[] {
  return [
    {
      key: "keyword",
      header: "Триггер",
      render: (item) => (
        <span className="font-medium text-(--color-ink)">{item.keyword}</span>
      ),
    },
    {
      key: "is_active",
      header: "Статус",
      render: (item) => (
        <span
          className={
            item.is_active ? "text-(--color-success)" : "text-(--color-muted)"
          }
        >
          {item.is_active ? "Активен" : "Приостановлен"}
        </span>
      ),
      filterOptions: STATUS_OPTIONS,
    },
  ];
}