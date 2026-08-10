"use client";

import { SearchInput } from "@/components/filters/SearchInput/SearchInput";
import { SelectFilter } from "@/components/filters/SelectFilter/SelectFilter";
import type { FilterOption } from "@/constants/roles";

type UserFiltersProps = {
  searchQuery: string;
  onSearchChange: (value: string) => void;

  departmentFilter: string;
  onDepartmentChange: (value: string) => void;
  departmentOptions: FilterOption[];

  statusFilter: string;
  onStatusChange: (value: string) => void;

  roleFilter: string;
  onRoleChange: (value: string) => void;
  roleOptions: FilterOption[];
};

const STATUS_OPTIONS: FilterOption[] = [
  { label: "Активен", value: "true" },
  { label: "Неактивен", value: "false" },
];

export function UserFilters({
  searchQuery,
  onSearchChange,
  departmentFilter,
  onDepartmentChange,
  departmentOptions,
  statusFilter,
  onStatusChange,
  roleFilter,
  onRoleChange,
  roleOptions,
}: UserFiltersProps) {
  return (
    <div className="mb-4 flex items-end justify-between gap-4 w-full">
      <SearchInput
        value={searchQuery}
        onChange={onSearchChange}
        placeholder="Поиск по пользователям..."
        className="w-full max-w-110"
      />

      <div className="flex gap-10">
        <SelectFilter
          label="Отдел"
          allLabel="Все отделы"
          value={departmentFilter}
          options={departmentOptions}
          onChange={onDepartmentChange}
          className="w-full max-w-51"
        />
        <SelectFilter
          label="Статус"
          allLabel="Все статусы"
          value={statusFilter}
          options={STATUS_OPTIONS}
          onChange={onStatusChange}
          className="w-full max-w-51"
        />
        <SelectFilter
          label="Роль"
          allLabel="Все роли"
          value={roleFilter}
          options={roleOptions}
          onChange={onRoleChange}
          className="w-full max-w-51"
        />
      </div>
    </div>
  );
}