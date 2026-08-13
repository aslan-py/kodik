// @/components/tables/IncidentTable.tsx
"use client";

import { FilterBar } from "@/components/filters/FilterBar/FilterBar";
import { Table, TableColumn } from "@/components/ui/Table/Table";
import type { FilterConfig } from "@/hooks/filters/types";
import type { FilterOption } from "@/types/types";

type IncidentTableProps<T> = {
  columns: TableColumn<T>[];
  data: T[];
  onRowClick: (item: T) => void;

  configs?: FilterConfig[];
  filterValues?: Record<string, string>;
  onFilterChange?: (key: string, value: string) => void;
  searchQuery?: string;
  onSearchChange?: (value: string) => void;
  dateFrom?: string;
  dateTo?: string;
  onDateFromChange?: (value: string) => void;
  onDateToChange?: (value: string) => void;
  dictOptions?: Record<string, FilterOption[]>;
  pageSize?: number;
  filtersKey?: string;
};

export default function IncidentTable<T>({
  columns,
  data,
  onRowClick,
  configs,
  filterValues,
  onFilterChange,
  searchQuery,
  onSearchChange,
  dateFrom = "",
  dateTo = "",
  onDateFromChange = () => {},
  onDateToChange = () => {},
  dictOptions,
  pageSize = 10,
  filtersKey,
}: IncidentTableProps<T>) {

  return (
    <>
      {configs && (
        <FilterBar
          configs={configs}
          filterValues={filterValues ?? {}}
          onFilterChange={onFilterChange ?? (() => {})}
          searchQuery={searchQuery ?? ""}
          onSearchChange={onSearchChange ?? (() => {})}
          dateFrom={dateFrom}
          dateTo={dateTo}
          onDateFromChange={onDateFromChange}
          onDateToChange={onDateToChange}
          dictOptions={dictOptions}
        />
      )}
      <Table
        data={data}
        columns={columns}
        pageSize={pageSize}
        resetPaginationKey={filtersKey}
        getRowKey={(item) => (item as { id?: number }).id ?? ""}
        onRowClick={onRowClick}
      />
    </>
  );
}
