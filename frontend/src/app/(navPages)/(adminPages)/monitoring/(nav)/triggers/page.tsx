"use client";

import { useMemo } from "react";
import MonitoringTable from "@/components/tables/MonitoringTable";
import { useTriggerColumns } from "@/components/tables/columns/triggerColumns";
import { useTableFilters } from "@/hooks/useTableFilters";
import { FilterConfig } from "@/hooks/filters/types";
import { MONITORING_STATUS_OPTIONS } from "@/types/types";
import { useGetTriggersQuery, TriggerQuery } from "@/api/monitoringApi";
import { buildApiParams } from "@/hooks/filters/buildApiParams";

const TRIGGER_FILTERS: FilterConfig[] = [
  {
    type: "search",
    key: "search",
    label: "Поиск по триггерам...",
    paramName: "q",
  },
  {
    type: "select",
    key: "is_active",
    label: "Статус",
    allLabel: "Все статусы",
    options: MONITORING_STATUS_OPTIONS,
    mapToApi: {
      active: true,
      "!active": false,
    },
  },
];

export default function TriggersPage() {
  const columns = useTriggerColumns();

  const {
    filterValues,
    setFilter,
    searchQuery,
    setSearchQuery,
    debouncedSearch,
    filtersKey,
  } = useTableFilters(TRIGGER_FILTERS);

  const apiParams = useMemo<TriggerQuery>(() => {
    return buildApiParams(
      TRIGGER_FILTERS,
      filterValues,
      debouncedSearch
    ) as TriggerQuery;
  }, [debouncedSearch, filterValues]);

  const { data: rows = [], isLoading } = useGetTriggersQuery(apiParams as TriggerQuery);

  return (
    <MonitoringTable
      columns={columns}
      rows={rows}
      isLoading={isLoading}
      pageSize={10}
      filtersKey={filtersKey}
      configs={TRIGGER_FILTERS}
      filterValues={filterValues}
      onFilterChange={setFilter}
      searchQuery={searchQuery}
      onSearchChange={setSearchQuery}
      dateFrom=""
      dateTo=""
      onDateFromChange={() => {}}
      onDateToChange={() => {}}
    />
  );
}
