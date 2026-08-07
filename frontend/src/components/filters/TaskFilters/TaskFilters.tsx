"use client";

import { PeriodSelector } from "@/components/filters/PeriodSelector/PeriodSelector";
import { SelectFilter } from "@/components/filters/SelectFilter/SelectFilter";

type FilterOption = { label: string; value: string };

type TaskFiltersProps = {
  statusFilter: string;
  onStatusChange: (value: string) => void;
  statusOptions: FilterOption[];
  dateFrom: string;
  dateTo: string;
  onDateFromChange: (value: string) => void;
  onDateToChange: (value: string) => void;
};

export function TaskFilters({
  statusFilter,
  onStatusChange,
  statusOptions,
  dateFrom,
  dateTo,
  onDateFromChange,
  onDateToChange,
}: TaskFiltersProps) {
  return (
    <div className="mb-4 flex flex-wrap items-end gap-4">
      <SelectFilter
        label="Статус"
        value={statusFilter}
        options={statusOptions}
        onChange={onStatusChange}
        className="w-full max-w-52"
      />
      <PeriodSelector
        dateFrom={dateFrom}
        dateTo={dateTo}
        onDateFromChange={onDateFromChange}
        onDateToChange={onDateToChange}
      />
    </div>
  );
}