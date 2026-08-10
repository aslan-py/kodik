"use client";

import { PeriodSelector } from "@/components/filters/PeriodSelector/PeriodSelector";
import { SelectFilter } from "@/components/filters/SelectFilter/SelectFilter";

type FilterOption = { label: string; value: string };
export type FilterKey =
  | "status"
  | "department"
  | "createdAt"
  | "updatedAt"
  | "deadline"
  | "period";
type TaskFiltersProps = {
  // статус
  statusFilter?: string;
  onStatusChange?: (value: string) => void;
  statusOptions?: FilterOption[];
  // отдел
  departmentFilter?: string;
  onDepartmentChange?: (value: string) => void;
  departmentOptions?: FilterOption[];
  // даты создания/обновления
  createdAtFilter?: string;
  onCreatedAtChange?: (value: string) => void;
  updatedAtFilter?: string;
  onUpdatedAtChange?: (value: string) => void;
  // дедлайн
  deadlineFilter?: string;
  onDeadlineChange?: (value: string) => void;
  // период
  dateFrom?: string;
  dateTo?: string;
  onDateFromChange?: (value: string) => void;
  onDateToChange?: (value: string) => void;
};

const createdAtOptions: FilterOption[] = [
  { label: "Сегодня", value: "today" },
  { label: "Вчера", value: "yesterday" },
  { label: "Неделя", value: "week" },
  { label: "Месяц", value: "month" },
];

const deadlineOptions: FilterOption[] = [
  { label: "Сегодня", value: "today" },
  { label: "Завтра", value: "tomorrow" },
  { label: "Неделя", value: "week" },
  { label: "Месяц", value: "month" },
  { label: "Просроченные", value: "overdue" },
];

export function TaskFilters({
  statusFilter,
  onStatusChange,
  statusOptions,
  departmentFilter,
  onDepartmentChange,
  departmentOptions,
  createdAtFilter,
  onCreatedAtChange,
  updatedAtFilter,
  onUpdatedAtChange,
  deadlineFilter,
  onDeadlineChange,
  dateFrom,
  dateTo,
  onDateFromChange,
  onDateToChange,
}: TaskFiltersProps) {
  return (
    <div className="mb-4 flex flex-wrap items-end gap-4">
      {onStatusChange && (
        <SelectFilter
          label="Статус"
          value={statusFilter ?? ""}
          options={statusOptions ?? []}
          onChange={onStatusChange}
          className="w-full max-w-52"
        />
      )}
      {onDepartmentChange && (
        <SelectFilter
          label="Отдел"
          value={departmentFilter ?? ""}
          options={departmentOptions ?? []}
          onChange={onDepartmentChange}
          className="w-full max-w-52"
        />
      )}
      {onCreatedAtChange && (
        <SelectFilter
          label="Создана"
          value={createdAtFilter ?? ""}
          options={createdAtOptions}
          onChange={onCreatedAtChange}
          className="w-full max-w-52"
        />
      )}
      {onUpdatedAtChange && (
        <SelectFilter
          label="Обновлена"
          value={updatedAtFilter ?? ""}
          options={createdAtOptions}
          onChange={onUpdatedAtChange}
          className="w-full max-w-52"
        />
      )}
      {onDeadlineChange && (
        <SelectFilter
          label="Срок"
          value={deadlineFilter ?? ""}
          options={deadlineOptions}
          onChange={onDeadlineChange}
          className="w-full max-w-52"
        />
      )}
      {onDateFromChange && onDateToChange && (
        <PeriodSelector
          dateFrom={dateFrom ?? ""}
          dateTo={dateTo ?? ""}
          onDateFromChange={onDateFromChange}
          onDateToChange={onDateToChange}
        />
      )}
    </div>
  );
}