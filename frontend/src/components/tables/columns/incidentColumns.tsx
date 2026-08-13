// @/components/tables/columns/incidentColumns.tsx
import { TableColumn } from "@/components/ui/Table/Table";
import { Showcase } from "@/api/showcaseApi";
import { shortMonthNames } from "@/helpers/date";
import { priorityClass } from "@/helpers/status";

export function useIncidentColumns(): TableColumn<Showcase>[] {
  return [
    {
      key: "published_at",
      header: "дата",
      width: "80px",
      className: "font-medium",
      render: (item) => {
        const d = new Date(item.published_at);
        return (
          <span className="block whitespace-nowrap">
            {d.getDate()} {shortMonthNames[d.getMonth()]}
          </span>
        );
      },
    },
    {
      key: "title",
      header: "событие",
      width: "450px",
      render: (item) => (
        <>
          <span className="block w-full text-(--color-ink) font-medium">{item.title}</span>
          {item.category && (
            <span className="inline-block text-(--color-muted) py-1 text-xs">{item.category}</span>
          )}
        </>
      ),
    },
    {
      key: "competitor",
      header: "Конкурент/объект",
      width: "190px",
      render: (item) => <span className="block text-(--color-strong)">{item.competitor}</span>,
    },
    {
      key: "source",
      header: "Источник",
      width: "180px",
      render: (item) => <span className="block text-(--color-secondary)">{item.media}</span>,
    },
    {
      key: "priority",
      header: "приоритет",
      width: "140px",
      render: (item) => <span className={priorityClass(item.priority ?? "")}>{item.priority}</span>,
    },
    {
      key: "index",
      header: "медиаиндекс",
      width: "160px",
      render: (item) => <span>{item.media_index}</span>,
    },
    {
      key: "tonality",
      header: "тональность",
      width: "224px",
      render: (item) => {
        const tonalityClass =
          item.tonality === "позитивная" ? "tonality tonality-positive"
          : item.tonality === "нейтральная" ? "tonality tonality-neutral"
          : item.tonality === "нерелевантная" ? "tonality tonality-spam"
          : "tonality tonality-negative";
        return <span className={tonalityClass}>{item.tonality}</span>;
      },
    },
  ];
}