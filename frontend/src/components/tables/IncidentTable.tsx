// @/components/tables/IncidentTable.tsx
"use client";

import { IncidentFilters } from "@/components/filters/IncidentFilters";
import { Table, TableColumn } from "@/components/ui/Table/Table";
import { Showcase, GetShowcasesParams } from "@/api/showcaseApi";
import { useFilteredIncidents } from "@/hooks/useFilteredIncidents";

type IncidentTableProps = {
  columns: TableColumn<Showcase>[];
  onOpen: (item: Showcase) => void;
  baseParams?: Partial<GetShowcasesParams>;
  showObjectFilter?: boolean;
  showDepartmentFilter?: boolean;
  showRegionFilter?: boolean;
};

export default function IncidentTable({
  columns,
  onOpen,
  baseParams,
  showObjectFilter = true,
  showDepartmentFilter = true,
  showRegionFilter = true,
}: IncidentTableProps) {
  const {
    incidents,
    isLoading,
    pageSize,
    filtersKey,
    handleReachLastPage,
    searchQuery,
    setSearchQuery,
    dateFrom,
    setDateFrom,
    dateTo,
    setDateTo,
    priorityFilter,
    setPriorityFilter,
    priorityOptions,
    objectFilter,
    setObjectFilter,
    objectOptions,
    departmentFilter,
    setDepartmentFilter,
    departmentOptions,
    regionFilter,
    setRegionFilter,
    regionOptions,
    usePeriod,
    setUsePeriod,
  } = useFilteredIncidents(baseParams);

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
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        dateFrom={dateFrom}
        dateTo={dateTo}
        onDateFromChange={setDateFrom}
        onDateToChange={setDateTo}
        usePeriod={usePeriod}
        onUsePeriodChange={setUsePeriod}
        priorityFilter={priorityFilter}
        onPriorityChange={setPriorityFilter}
        priorityOptions={priorityOptions}
        objectFilter={showObjectFilter ? objectFilter : undefined}
        onObjectChange={showObjectFilter ? setObjectFilter : undefined}
        objectOptions={objectOptions}
        departmentFilter={showDepartmentFilter ? departmentFilter : undefined}
        onDepartmentChange={
          showDepartmentFilter ? setDepartmentFilter : undefined
        }
        departmentOptions={departmentOptions}
        regionFilter={showRegionFilter ? regionFilter : undefined}
        onRegionChange={showRegionFilter ? setRegionFilter : undefined}
        regionOptions={regionOptions}
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
