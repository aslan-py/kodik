import type { FilterConfig } from "./types";
import { isSearch, isSelect, isPeriod } from "./types";

/**
 * Собирает параметры для API на основе конфигурации фильтров и их текущих значений.
 * Использует `mapToApi` для маппинга значений селектов, если указан.
 *
 * @param configs - Конфигурация фильтров
 * @param filterValues - Текущие значения фильтров (ключ → значение)
 * @param searchQuery - Текущее значение поиска (обычно debounced)
 * @param dateFrom - Начало периода (если есть фильтр периода)
 * @param dateTo - Конец периода (если есть фильтр периода)
 * @returns Объект параметров для API
 */
export function buildApiParams(
  configs: FilterConfig[],
  filterValues: Record<string, string>,
  searchQuery: string,
  dateFrom: string = "",
  dateTo: string = ""
): Record<string, any> {
  const params: Record<string, any> = {};

  // Обрабатываем каждый конфиг
  for (const config of configs) {
    // Поиск
    if (isSearch(config)) {
      if (searchQuery.trim()) {
        params[config.paramName] = searchQuery.trim();
      }
    }

    // Селект (статичный)
    if (isSelect(config)) {
      const value = filterValues[config.key];
      if (value) {
        // Если есть mapToApi, используем его для маппинга значения
        if (config.mapToApi && value in config.mapToApi) {
          params[config.key] = config.mapToApi[value];
        } else {
          // Иначе передаём значение как есть
          params[config.key] = value;
        }
      }
    }

    // Период
    if (isPeriod(config)) {
      if (dateFrom) params[config.paramFrom] = dateFrom;
      if (dateTo) params[config.paramTo] = dateTo;
    }
  }

  // Обрабатываем dict-select и deadline-select (они передаются как есть, без маппинга)
  for (const [key, value] of Object.entries(filterValues)) {
    // Пропускаем, если уже обработано выше
    const config = configs.find((c) => c.key === key);
    if (config && (isSearch(config) || isSelect(config) || isPeriod(config))) {
      continue;
    }
    // Для dict-select и deadline-select передаём значение как есть
    if (value) {
      params[key] = value;
    }
  }

  return params;
}
