"use client";

import { useMemo } from "react";
import MonitoringTable from "@/components/tables/MonitoringTable";
import { useCompetitorColumns } from "@/components/tables/columns/competitorColumns";
import { useTableFilters } from "@/hooks/useTableFilters";
import { FilterConfig } from "@/hooks/filters/types";
import { MONITORING_STATUS_OPTIONS } from "@/types/types";
import { useGetCompetitorsQuery, CompetitorQuery } from "@/api/monitoringApi";

const COMPETITOR_FILTERS: FilterConfig[] = [
  {
    type: "search",
    key: "search",
    label: "Поиск по конкурентам...",
    paramName: "q",
  },
  {
    type: "select",
    key: "is_active",
    label: "Статус",
    allLabel: "Все статусы",
    options: MONITORING_STATUS_OPTIONS,
  },
];

export default function CompetitorsPage() {
  const columns = useCompetitorColumns();

  const {
    filterValues,
    setFilter,
    searchQuery,
    setSearchQuery,
    debouncedSearch,
    filtersKey,
  } = useTableFilters(COMPETITOR_FILTERS);

  const apiParams = useMemo<CompetitorQuery>(() => {
    const params: CompetitorQuery = {};
    if (debouncedSearch.trim()) params.q = debouncedSearch.trim();
    const status = filterValues["is_active"];
    if (status === "active") params.is_active = true;
    else if (status === "!active") params.is_active = false;
    return params;
  }, [debouncedSearch, filterValues]);

  const { data: rows = [], isLoading } = useGetCompetitorsQuery(apiParams);

  return (
    <MonitoringTable
      columns={columns}
      rows={rows}
      isLoading={isLoading}
      pageSize={10}
      filtersKey={filtersKey}
      configs={COMPETITOR_FILTERS}
      filterValues={filterValues}
      onFilterChange={setFilter}
      searchQuery={searchQuery}
      onSearchChange={setSearchQuery}
    />
  );
}
