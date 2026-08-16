"use client";

import { SearchInput } from "@/components/filters/SearchInput/SearchInput";
import { SelectFilter } from "@/components/filters/SelectFilter/SelectFilter";
import { PeriodSelector } from "@/components/filters/PeriodSelector/PeriodSelector";
import type { FilterOption } from "@/types/types";
import type { FilterConfig } from "@/hooks/filters/types";
import { isSelect, isDictSelect, isPeriod, isSearch } from "@/hooks/filters/types";

type FilterBarProps = {
  configs: FilterConfig[];
  filterValues: Record<string, string>;
  onFilterChange: (key: string, value: string) => void;
  searchQuery: string;
  onSearchChange: (value: string) => void;
  dateFrom: string;
  dateTo: string;
  onDateFromChange: (value: string) => void;
  onDateToChange: (value: string) => void;
  /** Опции для dict-select фильтров (ключ → опции) */
  dictOptions?: Record<string, FilterOption[]>;
};

export function FilterBar({
  configs,
  filterValues,
  onFilterChange,
  searchQuery,
  onSearchChange,
  dateFrom,
  dateTo,
  onDateFromChange,
  onDateToChange,
  dictOptions = {},
}: FilterBarProps) {
  const selectConfigs = configs.filter((cfg) => isSelect(cfg) || isDictSelect(cfg));

  return (
    <div className="mb-4 flex flex-col gap-4 w-full">
      {/* Первая строка: поиск + период */}
      <div className="flex items-end gap-4 w-full">
        {configs.some(isSearch) && (
          <div className="flex-1 max-w-110">
            <SearchInput
              value={searchQuery}
              onChange={onSearchChange}
              placeholder="Поиск..."
              className="w-full"
            />
          </div>
        )}

        {configs.some(isPeriod) && (
          <PeriodSelector
            dateFrom={dateFrom}
            dateTo={dateTo}
            onDateFromChange={onDateFromChange}
            onDateToChange={onDateToChange}
          />
        )}
      </div>

      {/* Селект-фильтры */}
      {selectConfigs.length > 0 && (
        <div className="flex gap-10">
          {selectConfigs.map((cfg) => {
            const options = isSelect(cfg)
              ? cfg.options
              : dictOptions[cfg.key] ?? [];

            return (
              <SelectFilter
                key={cfg.key}
                label={cfg.label}
                allLabel={cfg.allLabel ?? "Все"}
                value={filterValues[cfg.key] ?? ""}
                options={options}
                onChange={(v) => onFilterChange(cfg.key, v)}
                className="w-full max-w-51"
              />
            );
          })}
        </div>
      )}
    </div>
  );
}