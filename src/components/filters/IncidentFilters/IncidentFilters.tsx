"use client";

import { SearchInput } from "@/components/filters/SearchInput/SearchInput";
import { PeriodSelector } from "@/components/filters/PeriodSelector/PeriodSelector";
import { SelectFilter } from "@/components/filters/SelectFilter/SelectFilter";

type FilterOption = { label: string; value: string };

type IncidentFiltersProps = {
  searchQuery: string;
  onSearchChange: (value: string) => void;
  dateFrom: string;
  dateTo: string;
  onDateFromChange: (value: string) => void;
  onDateToChange: (value: string) => void;
  sourceFilter: string;
  onSourceChange: (value: string) => void;
  sourceOptions: FilterOption[];
  priorityFilter: string;
  onPriorityChange: (value: string) => void;
  priorityOptions: FilterOption[];
  objectFilter: string;
  onObjectChange: (value: string) => void;
  objectOptions: FilterOption[];
};

export function IncidentFilters({
  searchQuery,
  onSearchChange,
  dateFrom,
  dateTo,
  onDateFromChange,
  onDateToChange,
  sourceFilter,
  onSourceChange,
  sourceOptions,
  priorityFilter,
  onPriorityChange,
  priorityOptions,
  objectFilter,
  onObjectChange,
  objectOptions,
}: IncidentFiltersProps) {
  return (
    <div className="mb-4 grid grid-cols-[1fr_1fr_auto] gap-x-6 gap-y-4 items-end">
      <div className="flex items-end gap-4 max-w-110">
        <SearchInput
          value={searchQuery}
          onChange={onSearchChange}
          placeholder="Событие, компания, источник..."
          className="w-full"
        />
      </div>
      <div />
      <PeriodSelector
        dateFrom={dateFrom}
        dateTo={dateTo}
        onDateFromChange={onDateFromChange}
        onDateToChange={onDateToChange}
      />
      <div className="flex items-end gap-4">
        <SelectFilter
          label="Источник"
          value={sourceFilter}
          options={sourceOptions}
          onChange={onSourceChange}
          className="w-full max-w-51"
        />
        <SelectFilter
          label="Приоритет"
          value={priorityFilter}
          options={priorityOptions}
          onChange={onPriorityChange}
          className="w-full max-w-51"
        />
      </div>
      <SelectFilter
        label="Объект"
        value={objectFilter}
        options={objectOptions}
        onChange={onObjectChange}
        className="w-full max-w-51"
      />
      <div />
    </div>
  );
}