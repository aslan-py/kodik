// @/hooks/useLabelMap.ts
import { useMemo } from "react";

export interface LabelOption<T extends string | number = string> {
  label: string;
  value: T;
}

export function useLabelMap<T extends string | number>(
  options: LabelOption<T>[] | undefined,
) {
  return useMemo(
    () => new Map(options?.map((o) => [o.value, o.label]) ?? []),
    [options],
  );
}

export function labelFromMap<T extends string | number>(
  map: Map<T, string>,
  value: T | null | undefined,
  fallback = "—",
): string {
  if (value == null) return fallback;
  return map.get(value) ?? fallback;
}
export function useLabelFor<T extends string | number>(
  options: LabelOption<T>[] | undefined,
  value: T | null | undefined,
  fallback = "—",
): string {
  const map = useLabelMap(options);
  if (value == null) return fallback;
  return map.get(value) ?? fallback;
}

// для статических констант хук не нужен — опции и так стабильная ссылка
export function getLabel<T extends string | number>(
  options: LabelOption<T>[],
  value: T | null | undefined,
  fallback = "—",
): string {
  if (value == null) return fallback;
  return options.find((o) => o.value === value)?.label ?? fallback;
}


export function uniqueOptionsFromData<T, V extends string>(
  items: T[],
  field: (item: T) => V | null | undefined,
  labelMap?: Record<V, string> | Map<V, string>,
): LabelOption<V>[] {
  const values = new Set<V>();
  for (const item of items) {
    const v = field(item);
    if (v != null) values.add(v);
  }

  const resolveLabel = (v: V): string =>
    labelMap instanceof Map ? (labelMap.get(v) ?? v) : (labelMap?.[v] ?? v);

  return [...values]
    .map((value) => ({ label: resolveLabel(value), value }))
    .sort((a, b) => a.label.localeCompare(b.label, "ru"));
}