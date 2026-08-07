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
    <div className="mb-4 flex flex-col gap-x-6 gap-y-4">
      <div className="flex justify-between items-end gap-4 w-full
      ">
        <SearchInput
          value={searchQuery}
          onChange={onSearchChange}
          placeholder="Событие, компания, источник..."
          className="w-full max-w-110"
        />
        <PeriodSelector
          dateFrom={dateFrom}
          dateTo={dateTo}
          onDateFromChange={onDateFromChange}
          onDateToChange={onDateToChange}
        />
      </div>
    <div />

    <div className="flex gap-10">
        <SelectFilter
          label="Источник"
          allLabel="Все источники"
          value={sourceFilter}
          options={sourceOptions}
          onChange={onSourceChange}
          className="w-full max-w-51"
        />
        <SelectFilter
          label="Приоритет"
          allLabel="Все приоритеты"
          value={priorityFilter}
          options={priorityOptions}
          onChange={onPriorityChange}
          className="w-full max-w-51"
        />
      <SelectFilter
        label="Объект"
        allLabel="Все объекты"
        value={objectFilter}
        options={objectOptions}
        onChange={onObjectChange}
        className="w-full max-w-51"
      />
      </div>
      <div />
    </div>
  );
}
