// @/components/tables/columns/competitorColumns.tsx
import { TableColumn } from "@/components/ui/Table/Table";
import { Competitor } from "@/api/monitoringApi";

const STATUS_OPTIONS = [
  { label: "Активный", value: "1" },
  { label: "Приостановлен", value: "0" },
];

export function useCompetitorColumns(): TableColumn<Competitor>[] {
  return [
    {
      key: "name",
      header: "Конкурент",
      render: (item) => (
        <span className="font-medium text-(--color-ink)">{item.name}</span>
      ),
    },
    {
      key: "inn",
      header: "ИНН",
      render: (item) => <span>{item.inn}</span>,
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