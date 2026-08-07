"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { IncidentFilters } from "@/components/filters/IncidentFilters";
import { Table, TableColumn } from "@/components/ui/Table/Table";
import { shortMonthNames } from "@/helpers/date";
import { priorityClass } from "@/helpers/status";
import {
  useGetShowcasesQuery,
  Showcase,
  GetShowcasesParams,
} from "@/api/showcaseApi";

function useIncidentColumns(): TableColumn<Showcase>[] {
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
          <span className="block w-full text-(--color-ink) font-medium">
            {item.title}
          </span>
          {item.category && (
            <span className="inline-block text-(--color-muted) py-1 text-xs">
              {item.category}
            </span>
          )}
        </>
      ),
    },
    {
      key: "competitor",
      header: "Конкурент/объект",
      width: "190px",
      render: (item) => (
        <span className="block text-(--color-strong)">{item.competitor}</span>
      ),
    },
    {
      key: "source",
      header: "Источник",
      width: "180px",
      render: (item) => (
        <span className="block text-(--color-secondary)">{item.media}</span>
      ),
    },
    {
      key: "priority",
      header: "приоритет",
      width: "140px",
      render: (item) => (
        <span className={priorityClass(item.priority ?? "")}>
          {item.priority}
        </span>
      ),
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
          item.tonality === "позитивная"
            ? "tonality tonality-positive"
            : item.tonality === "нейтральная"
              ? "tonality tonality-neutral"
              : item.tonality === "нерелевантная"
                ? "tonality tonality-spam"
                : "tonality tonality-negative";
        return <span className={tonalityClass}>{item.tonality}</span>;
      },
    },
  ];
}

function getUniqueOptions(
  items: Showcase[],
  field: keyof Pick<Showcase, "region" | "priority" | "competitor">,
) {
  const values = [...new Set(items.map((item) => item[field]))];
  return values
    .filter((v): v is string => v != null)
    .map((value) => ({ label: value, value }));
}

function getDefaultDateRange(): { from: string; to: string } {
  const now = new Date();
  const from = new Date(now);
  from.setDate(from.getDate() - 29);
  return {
    from: from.toISOString().slice(0, 10),
    to: now.toISOString().slice(0, 10),
  };
}

const defaultRange = getDefaultDateRange();

type IncidentTableProps = {
  onOpen: (item: Showcase) => void;
};

export default function IncidentTable({ onOpen }: IncidentTableProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const [dateFrom, setDateFrom] = useState(defaultRange.from);
  const [dateTo, setDateTo] = useState(defaultRange.to);
  const [sourceFilter, setSourceFilter] = useState("");
  const [priorityFilter, setPriorityFilter] = useState("");
  const [objectFilter, setObjectFilter] = useState("");
  const [page, setPage] = useState(1);
  const [limit, setLimit] = useState(50);
  const pageSize = 10;
  const columns = useIncidentColumns();

  const filtersKey = `${searchQuery}-${dateFrom}-${dateTo}-${sourceFilter}-${priorityFilter}-${objectFilter}`;

  const params = useMemo<GetShowcasesParams>(() => {
    const p: GetShowcasesParams = {
      limit,
      offset: (page - 1) * pageSize,
    };
    if (searchQuery.trim()) p.title = searchQuery.trim();
    if (dateFrom) p.published_from = dateFrom;
    if (dateTo) p.published_to = dateTo;
    if (sourceFilter) p.region = sourceFilter;
    if (priorityFilter) p.priority = priorityFilter;
    if (objectFilter) p.competitor = objectFilter;
    return p;
  }, [
    page,
    limit,
    searchQuery,
    dateFrom,
    dateTo,
    sourceFilter,
    priorityFilter,
    objectFilter,
  ]);

  const { data: incidents = [], isLoading } = useGetShowcasesQuery(params);
  const { data: allIncidents = [] } = useGetShowcasesQuery({ limit: 50 });

  const handleReachLastPage = useCallback(() => {
    setLimit((prev) => prev + 50);
  }, []);

  useEffect(() => {
    setPage(1);
  }, [filtersKey]);

  const sourceOptions = useMemo(
    () => getUniqueOptions(allIncidents, "region"),
    [allIncidents],
  );
  const priorityOptions = useMemo(
    () => getUniqueOptions(allIncidents, "priority"),
    [allIncidents],
  );
  const objectOptions = useMemo(
    () => getUniqueOptions(allIncidents, "competitor"),
    [allIncidents],
  );

  if (isLoading) {
    return (
      <div className="text-sm text-(--color-muted) py-8">
        Загрузка витрины...
      </div>
    );
  }

  return (
    <>
      <IncidentFilters
        // поиск
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}

        // селектор дат
        dateFrom={dateFrom}
        dateTo={dateTo}
        onDateFromChange={setDateFrom}
        onDateToChange={setDateTo}
        // фильтр источников
        sourceFilter={sourceFilter}
        onSourceChange={setSourceFilter}
        sourceOptions={sourceOptions}
        // фильтр приориета
        priorityFilter={priorityFilter}
        onPriorityChange={setPriorityFilter}
        priorityOptions={priorityOptions}
        // фильтр конкурентов
        objectFilter={objectFilter}
        onObjectChange={setObjectFilter}
        objectOptions={objectOptions}
      />
      <Table
        data={incidents}
        columns={columns}
        pageSize={pageSize}
        onReachLastPage={handleReachLastPage}
        onRowClick={onOpen}
        resetPaginationKey={filtersKey}
      />
    </>
  );
}
