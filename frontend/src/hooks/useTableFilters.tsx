import { useMemo, useState, useCallback } from "react";
import { useDebounce } from "@/hooks/useDebounce";
import {
  FilterConfig,
  isPeriod,
} from "./filters/types";
import { getPresetRange } from "@/helpers/date";

export function useTableFilters(configs: FilterConfig[]) {
  const [searchQuery, setSearchQuery] = useState("");
  const debouncedSearch = useDebounce(searchQuery, 400);

  const [filterValues, setFilterValues] = useState<Record<string, string>>({});

// ! период по умолчанию 30 дней
  const defaultRange = useMemo(() => getPresetRange("30days"), []);
  const [dateFrom, setDateFrom] = useState(defaultRange.from);
  const [dateTo, setDateTo] = useState(defaultRange.to);
  const setFilter = useCallback((key: string, value: string) => {
    setFilterValues((prev: Record<string, string>) => ({ ...prev, [key]: value }));
  }, []);

  const resetFilters = useCallback(() => {
    setSearchQuery("");
    setFilterValues({});
    setDateFrom("");
    setDateTo("");
  }, []);

  // Собираем filtersKey для сброса пагинации
  const filtersKey = useMemo(() => {
    return [
      debouncedSearch,
      ...configs.map((cfg) => {
        if (isPeriod(cfg)) {
          return `${cfg.key}:${dateFrom}:${dateTo}`;
        }
        return `${cfg.key}:${filterValues[cfg.key] ?? ""}`;
      }),
    ].join("|");
  }, [configs, filterValues, debouncedSearch, dateFrom, dateTo]);

  return {
    filterValues,
    setFilter,
    searchQuery,
    setSearchQuery,
    debouncedSearch,
    dateFrom,
    setDateFrom,
    dateTo,
    setDateTo,
    filtersKey,
    resetFilters,
  };
}


  