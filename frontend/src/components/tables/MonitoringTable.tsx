"use client";

import { Table, TableColumn } from "@/components/ui/Table/Table";
import { FilterBar } from "@/components/filters/FilterBar/FilterBar";
import type { FilterConfig } from "@/hooks/filters/types";
import type { FilterOption } from "@/types/types";

type MonitoringTableProps<T> = {
  columns: TableColumn<T>[];
  rows: T[];
  isLoading: boolean;
  pageSize: number;
  filtersKey: string;

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
};

export default function MonitoringTable<T>({
  columns,
  rows,
  isLoading,
  pageSize,
  filtersKey,
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
}: MonitoringTableProps<T>) {
  if (isLoading) {
    return (
      <div className="text-sm text-(--color-muted) py-8">Загрузка...</div>
    );
  }

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
        data={rows}
        columns={columns}
        pageSize={pageSize}
        resetPaginationKey={filtersKey}
        getRowKey={(item) =>
          (item as { id?: number }).id ?? `${filtersKey}-${rows.indexOf(item)}`
        }
      />
    </>
  );
}