"use client";

import { Table, TableColumn } from "@/components/ui/Table/Table";
import { ActionItem } from "@/api/actionApi";

import { FilterBar } from "../filters/FilterBar/FilterBar";
import type { FilterConfig } from "@/hooks/filters/types";
import type { FilterOption } from "@/types/types";

type TaskTableProps = {
  tasks: ActionItem[];
  columns: TableColumn<ActionItem>[];
  onOpen?: (task: ActionItem) => void;

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
  filtersKey?: string;
};

export default function TaskTable({
  tasks,
  columns,
  onOpen,
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
  filtersKey,
}: TaskTableProps) {
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
        data={tasks}
        columns={columns}
        pageSize={10}
        getRowKey={(item) => item.id}
        resetPaginationKey={filtersKey}
        onRowClick={onOpen}
      />
    </>
  );
}
