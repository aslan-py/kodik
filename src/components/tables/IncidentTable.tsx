"use client";

import { useMemo, useState } from "react";
import { Button } from "@/components/ui/Button/button";
import { IncidentFilters } from "@/components/filters/IncidentFilters";
import { Table, TableColumn } from "@/components/ui/Table/Table";
import { Icon } from "@/components/ui/Icon/Icon";
import { shortMonthNames, parseDotDate } from "@/helpers/date";
import { IncidentItem } from "@/types/types";
import { mockIncidents } from "@/data/mockIncidents";

function useIncidentColumns(
  onOpen: (item: IncidentItem) => void,
): TableColumn<IncidentItem>[] {
  return [
    {
      key: "data",
      header: "дата",
      width: "80px",
      className: "font-medium",
      render: (item: IncidentItem) => {
        const [day, month] = item.data.split(".").map(Number);
        return (
          <span className="block whitespace-nowrap">
            {day} {shortMonthNames[month - 1]}
          </span>
        );
      },
    },
    {
      key: "incident",
      header: "событие",
      className: "",
      render: (item: IncidentItem) => (
        <>
          <span className="block text-(--color-ink) font-medium">
            {item.incident}
          </span>

          {/* ! времено */}
          <span className="inline-block text-(--color-muted) py-1 text-xs">
            {item.type} • {item.category}
          </span>
        </>
      ),
    },
    {
      key: "object",
      header: "объект",
      render: (item: IncidentItem) => (
        <>
          <span className="block text-(--color-strong)">{item.object}</span>
        </>
      ),
    },
    {
      key: "source",
      header: "источник",
      render: (item: IncidentItem) => (
        <>
          <span className="block text-(--color-secondary)">{item.source}</span>
        </>
      ),
    },
    {
      key: "priority",
      header: "приоритет",
      render: (item: IncidentItem) => {
        const priorityClass =
          item.priority === "П1"
            ? "priority priority-accent"
            : item.priority === "П2"
              ? "priority priority-strong"
              : "priority priority-muted";
        return <span className={priorityClass}>{item.priority}</span>;
      },
    },
    { key: "index", header: "медиаиндекс" },
    {
      key: "tonality",
      header: "тональность",
      render: (item: IncidentItem) => {
        const tonalityClass =
          item.tonality === "Позитивная"
            ? "tonality tonality-positive"
            : item.tonality === "Нейтральная"
              ? "tonality tonality-neutral"
              : "tonality tonality-negative";
        return <span className={tonalityClass}>{item.tonality}</span>;
      },
    },
    {
      key: "button",
      header: "",
      render: (item: IncidentItem) => (
        <Button
          variant="tertiary"
          onClick={() => onOpen(item)}
          endIcon={<Icon name="link" />}
          className="hover:text-(--color-accent)"
        >
          Открыть
        </Button>
      ),
    },
  ];
}

function getUniqueOptions(
  items: IncidentItem[],
  field: keyof Pick<IncidentItem, "source" | "priority" | "object">,
) {
  const values = [...new Set(items.map((item) => item[field]))];
  return values.map((value) => ({ label: value, value }));
}
// выбор дат по умолчанию
function getDefaultDateRange(): { from: string; to: string } {
  const now = new Date();
  const from = new Date(now);
  from.setDate(from.getDate() - 29);
  const toStr = now.toISOString().slice(0, 10);
  const fromStr = from.toISOString().slice(0, 10);
  return { from: fromStr, to: toStr };
}

const defaultRange = getDefaultDateRange();

type IncidentTableProps = {
  onOpen: (item: IncidentItem) => void;
};

export default function IncidentTable({ onOpen }: IncidentTableProps) {
  const incidents = useMemo(() => mockIncidents, []);
  const [searchQuery, setSearchQuery] = useState("");
  const [dateFrom, setDateFrom] = useState(defaultRange.from);
  const [dateTo, setDateTo] = useState(defaultRange.to);
  const [sourceFilter, setSourceFilter] = useState("");
  const [priorityFilter, setPriorityFilter] = useState("");
  const [objectFilter, setObjectFilter] = useState("");
  const columns = useIncidentColumns(onOpen);

  const sourceOptions = useMemo(
    () => getUniqueOptions(incidents, "source"),
    [incidents],
  );

  const priorityOptions = useMemo(
    () => getUniqueOptions(incidents, "priority"),
    [incidents],
  );

  const objectOptions = useMemo(
    () => getUniqueOptions(incidents, "object"),
    [incidents],
  );

  const filteredIncidents = useMemo(
    () =>
      incidents
        .filter((item) => {
          const q = searchQuery.toLowerCase().trim();
          const matchesSearch =
            !q ||
            item.incident.toLowerCase().includes(q) ||
            item.object.toLowerCase().includes(q) ||
            item.source.toLowerCase().includes(q);
          const matchesSource = !sourceFilter || item.source === sourceFilter;
          const matchesPriority =
            !priorityFilter || item.priority === priorityFilter;
          const matchesObject = !objectFilter || item.object === objectFilter;

          const itemDate = parseDotDate(item.data);
          const matchesDateFrom =
            !dateFrom || itemDate >= new Date(dateFrom + "T00:00:00");
          const matchesDateTo =
            !dateTo ||
            itemDate <=
              new Date(new Date(dateTo + "T00:00:00").getTime() + 86400000);

          return (
            matchesSearch &&
            matchesSource &&
            matchesPriority &&
            matchesObject &&
            matchesDateFrom &&
            matchesDateTo
          );
        })
        .sort((a, b) => {
          const [aDay, aMonth, aYear] = a.data.split(".").map(Number);
          const [bDay, bMonth, bYear] = b.data.split(".").map(Number);
          const aTs = new Date(aYear, aMonth - 1, aDay).getTime();
          const bTs = new Date(bYear, bMonth - 1, bDay).getTime();
          return bTs - aTs; // сначала новые
        }),
    [
      incidents,
      searchQuery,
      sourceFilter,
      priorityFilter,
      objectFilter,
      dateFrom,
      dateTo,
    ],
  );

  return (
    <>
      <IncidentFilters
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        dateFrom={dateFrom}
        dateTo={dateTo}
        onDateFromChange={setDateFrom}
        onDateToChange={setDateTo}
        sourceFilter={sourceFilter}
        onSourceChange={setSourceFilter}
        sourceOptions={sourceOptions}
        priorityFilter={priorityFilter}
        onPriorityChange={setPriorityFilter}
        priorityOptions={priorityOptions}
        objectFilter={objectFilter}
        onObjectChange={setObjectFilter}
        objectOptions={objectOptions}
      />
      <Table
        data={filteredIncidents}
        columns={columns}
        pageSize={3}
        resetPaginationKey={`${searchQuery}-${dateFrom}-${dateTo}-${sourceFilter}-${priorityFilter}-${objectFilter}`}
      />
    </>
  );
}
