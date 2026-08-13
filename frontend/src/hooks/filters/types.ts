import type { FilterOption } from "@/types/types";

type BaseConfig = {
  key: string;
  label: string;
  allLabel?: string;
};

/** Статичные опции (статусы, приоритеты — из констант) */
export type StaticSelectConfig = BaseConfig & {
  type: "select";
  options: FilterOption[];
  /** Маппинг значения селекта → значение параметра API */
  mapToApi?: Record<string, string | boolean | number>;
};

/** Опции из справочника — передаются через props на уровне страницы */
export type DictSelectConfig = BaseConfig & {
  type: "dict-select";
  /** Маппинг значения селекта → значение параметра API (опционально) */
  mapToApi?: Record<string, string | boolean | number>;
};

/** Клиентская фильтрация по дедлайну */
export type DeadlineSelectConfig = BaseConfig & {
  type: "deadline-select";
  options: FilterOption[];
  /** Маппинг значения селекта → значение параметра API (опционально) */
  mapToApi?: Record<string, string | boolean | number>;
};
/** Период (от/до) */
export type PeriodConfig = BaseConfig & {
  type: "period";
  paramFrom: string;
  paramTo: string;
};

/** Текстовый поиск */
export type SearchConfig = BaseConfig & {
  type: "search";
  paramName: string;
  debounceMs?: number;
};

export type FilterConfig =
  | StaticSelectConfig
  | DictSelectConfig
  | DeadlineSelectConfig
  | PeriodConfig
  | SearchConfig;

/* Type guards */
export function isSelect(cfg: FilterConfig): cfg is StaticSelectConfig {
  return cfg.type === "select";
}

export function isDictSelect(cfg: FilterConfig): cfg is DictSelectConfig {
  return cfg.type === "dict-select";
}

export function isDeadlineSelect(cfg: FilterConfig): cfg is DeadlineSelectConfig {
  return cfg.type === "deadline-select";
}

export function isPeriod(cfg: FilterConfig): cfg is PeriodConfig {
  return cfg.type === "period";
}

export function isSearch(cfg: FilterConfig): cfg is SearchConfig {
  return cfg.type === "search";
}