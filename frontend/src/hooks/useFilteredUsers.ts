"use client";

import { useMemo, useState } from "react";
import { useDebounce } from "@/hooks/useDebounce";
import { useGetAllUsersQuery } from "@/api/usersApi";
import { ROLE_OPTIONS } from "@/constants/roles";
import { useGetDepartmentsQuery } from "@/api/adminSourceApi";

const PAGE_SIZE = 10;

export function useFilteredUsers() {
  const [searchQuery, setSearchQuery] = useState("");
  const debouncedSearch = useDebounce(searchQuery, 400);

  const [departmentFilter, setDepartmentFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [roleFilter, setRoleFilter] = useState("");

  const filtersKey = [debouncedSearch, departmentFilter, statusFilter, roleFilter].join("|");

  // department_id — единственный поддерживаемый бэком фильтр,
  // остальное (search по full_name/email, status, role) фильтруем на клиенте
  const { data, isLoading } = useGetAllUsersQuery({
    department_id: departmentFilter ? Number(departmentFilter) : undefined,
  });

  const users = useMemo(() => {
    if (!data) return [];
    const query = debouncedSearch.trim().toLowerCase();

    return data.filter((user) => {
      if (query) {
        const matches =
          user.full_name.toLowerCase().includes(query) ||
          user.email.toLowerCase().includes(query);
        if (!matches) return false;
      }
      if (statusFilter && String(user.is_active) !== statusFilter) return false;
      if (roleFilter && user.role !== roleFilter) return false;
      return true;
    });
  }, [data, debouncedSearch, statusFilter, roleFilter]);

  const { data: departments } = useGetDepartmentsQuery();
  const departmentOptions = useMemo(
    () => departments?.map((d) => ({ label: d.name, value: String(d.id) })) ?? [],
    [departments],
  );

  return {
    users,
    isLoading,
    pageSize: PAGE_SIZE,
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
    roleOptions: ROLE_OPTIONS,
  };
}