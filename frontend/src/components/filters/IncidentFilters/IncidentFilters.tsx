"use client";

import { SearchInput } from "@/components/filters/SearchInput/SearchInput";
import { PeriodSelector } from "@/components/filters/PeriodSelector/PeriodSelector";
import { SelectFilter } from "@/components/filters/SelectFilter/SelectFilter";
import { Checkbox } from "@/components/ui/Checkbox/Checkbox";

type FilterOption = { label: string; value: string };

type IncidentFiltersProps = {
  searchQuery: string;
  onSearchChange: (value: string) => void;
  dateFrom: string;
  dateTo: string;
  onDateFromChange: (value: string) => void;
  onDateToChange: (value: string) => void;
  usePeriod: boolean;
  onUsePeriodChange: (value: boolean) => void;

  // TODO: источник (поиск по media) — вернуть, когда появится поле в API
  // sourceFilter: string;
  // onSourceChange: (value: string) => void;
  // sourceOptions: FilterOption[];

  priorityFilter: string;
  onPriorityChange: (value: string) => void;
  priorityOptions: FilterOption[];

  objectFilter?: string;
  onObjectChange?: (value: string) => void;
  objectOptions?: FilterOption[];

  departmentFilter?: string;
  onDepartmentChange?: (value: string) => void;
  departmentOptions?: FilterOption[];

  regionFilter?: string;
  onRegionChange?: (value: string) => void;
  regionOptions?: FilterOption[];
};

export function IncidentFilters({
  searchQuery,
  onSearchChange,
  dateFrom,
  dateTo,
  onDateFromChange,
  onDateToChange,
  usePeriod,
  onUsePeriodChange,
  // sourceFilter,
  // onSourceChange,
  // sourceOptions,
  priorityFilter,
  onPriorityChange,
  priorityOptions,
  objectFilter,
  onObjectChange,
  objectOptions,
  departmentFilter,
  onDepartmentChange,
  departmentOptions,
  regionFilter,
  onRegionChange,
  regionOptions,
}: IncidentFiltersProps) {
  return (
    <div className="mb-4 flex flex-col gap-x-6 gap-y-4">
      <div className="flex justify-between items-end gap-4 w-full">
        <div className="flex flex-col w-full max-w-110">
          <SearchInput
            value={searchQuery}
            onChange={onSearchChange}
            placeholder="Событие, компания, источник..."
            className="mb-1"
          />
          <Checkbox
            className="text-xs search-checkbox"
            label="Включить период в поиск"
            checked={usePeriod}
            onChange={onUsePeriodChange}
          />
        </div>
        <div className="flex items-center gap-4">
          <PeriodSelector
            dateFrom={dateFrom}
            dateTo={dateTo}
            onDateFromChange={onDateFromChange}
            onDateToChange={onDateToChange}
          />
        </div>
      </div>
      <div />

      <div className="flex gap-10">
        {/* TODO: источник — вернуть, когда появится поле в API
        <SelectFilter
          label="Источник"
          allLabel="Все источники"
          value={sourceFilter}
          options={sourceOptions}
          onChange={onSourceChange}
          className="w-full max-w-51"
        />
        */}
        <SelectFilter
          label="Приоритет"
          allLabel="Все приоритеты"
          value={priorityFilter}
          options={priorityOptions}
          onChange={onPriorityChange}
          className="w-full max-w-51"
        />
        {onObjectChange && (
          <SelectFilter
            label="Объект"
            allLabel="Все объекты"
            value={objectFilter ?? ""}
            options={objectOptions ?? []}
            onChange={onObjectChange}
            className="w-full max-w-51"
          />
        )}
        {onDepartmentChange && (
          <SelectFilter
            label="Отдел"
            allLabel="Все отделы"
            value={departmentFilter ?? ""}
            options={departmentOptions ?? []}
            onChange={onDepartmentChange}
            className="w-full max-w-51"
          />
        )}
        {onRegionChange && (
          <SelectFilter
            label="Регион"
            allLabel="Все регионы"
            value={regionFilter ?? ""}
            options={regionOptions ?? []}
            onChange={onRegionChange}
            className="w-full max-w-51"
          />
        )}
      </div>
      <div />
    </div>
  );
}