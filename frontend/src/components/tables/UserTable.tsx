"use client";

import { useState } from "react";
import { Table, TableColumn } from "@/components/ui/Table/Table";
import { useFilteredUsers } from "@/hooks/useFilteredUsers";
import { UserFilters } from "../filters/UserFilters/UserFilters";
import { EditUserRoleModal } from "@/components/forms/EditUserRoleModal";
import { AuthUser } from "@/store/authSlice";
import { useUserColumns } from "@/components/tables/columns/userColumns";

type UserTableProps = {
  columns: TableColumn<AuthUser>[];
};

export default function UserTable() { 
  const columns = useUserColumns((user) => setEditingUser(user));
  const {
    users,
    isLoading,
    pageSize,
    filtersKey,
    searchQuery,
    setSearchQuery,
    departmentFilter,
    setDepartmentFilter,
    departmentOptions,
    statusFilter,
    setStatusFilter,
    roleFilter,
    setRoleFilter,
    roleOptions,
  } = useFilteredUsers();

  const [editingUser, setEditingUser] = useState<AuthUser | null>(null);

  if (isLoading) {
    return (
      <div className="text-sm text-(--color-muted) py-8">
        Загрузка пользователей...
      </div>
    );
  }

  return (
    <>
      <UserFilters
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        departmentFilter={departmentFilter}
        onDepartmentChange={setDepartmentFilter}
        departmentOptions={departmentOptions}
        statusFilter={statusFilter}
        onStatusChange={setStatusFilter}
        roleFilter={roleFilter}
        onRoleChange={setRoleFilter}
        roleOptions={roleOptions}
      />
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