"use client";

import { useState } from "react";
import { Table } from "@/components/ui/Table/Table";
import { FilterBar } from "@/components/filters/FilterBar/FilterBar";
import { EditUserRoleModal } from "@/components/forms/EditUserRoleModal";
import { AuthUser } from "@/store/authSlice";
import { useUserColumns } from "@/components/tables/columns/userColumns";
import type { FilterConfig } from "@/hooks/filters/types";
import type { FilterOption } from "@/types/types";

type UserTableProps = {
  users: AuthUser[];
  isLoading: boolean;
  pageSize: number;
  filtersKey: string;

  configs?: FilterConfig[];
  filterValues?: Record<string, string>;
  onFilterChange?: (key: string, value: string) => void;
  searchQuery?: string;
  onSearchChange?: (value: string) => void;
  dateFrom?: string;
  dateTo?: string;
  onDateFromChange?: (value: string) => void;
  onDateToChange?: (value: string) => void;
  dictOptions?: Record<string, FilterOption[]>;
};

export default function UserTable({
  users,
  isLoading,
  pageSize,
  filtersKey,
  configs,
  filterValues,
  onFilterChange,
  searchQuery,
  onSearchChange,
  dateFrom = "",
  dateTo = "",
  onDateFromChange = () => {},
  onDateToChange = () => {},
  dictOptions,
}: UserTableProps) {
  const [editingUser, setEditingUser] = useState<AuthUser | null>(null);
  const columns = useUserColumns((user) => setEditingUser(user));

  if (isLoading) {
    return (
      <div className="text-sm text-(--color-muted) py-8">
        Загрузка пользователей...
      </div>
    );
  }

  return (
    <>
      {configs && (
        <FilterBar
          configs={configs}
          filterValues={filterValues ?? {}}
          onFilterChange={onFilterChange ?? (() => {})}
          searchQuery={searchQuery ?? ""}
          onSearchChange={onSearchChange ?? (() => {})}
          dateFrom={dateFrom}
          dateTo={dateTo}
          onDateFromChange={onDateFromChange}
          onDateToChange={onDateToChange}
          dictOptions={dictOptions}
        />
      )}
      <Table
        data={users}
        columns={columns}
        pageSize={pageSize}
        resetPaginationKey={filtersKey}
        getRowKey={(user) => user.id}
      />
      <EditUserRoleModal user={editingUser} onClose={() => setEditingUser(null)} />
    </>
  );
}
