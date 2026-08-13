"use client"
import { useMemo } from "react";
import UserTable from "@/components/tables/UserTable";
import TitlePage from "@/components/layout/TitlePage";
import { useTableFilters } from "@/hooks/useTableFilters";
import { FilterConfig } from "@/hooks/filters/types";
import { ROLE_OPTIONS } from "@/constants/roles";
import { useGetAllUsersQuery } from "@/api/usersApi";
import { useGetDepartmentsQuery } from "@/api/adminSourceApi";
import { AuthUser } from "@/store/authSlice";
import { buildApiParams } from "@/hooks/filters/buildApiParams";

const PAGE_SIZE = 10;

const STATUS_OPTIONS = [
  { label: "Активен", value: "true" },
  { label: "Неактивен", value: "false" },
];

const USER_FILTERS: FilterConfig[] = [
  {
    type: "search",
    key: "search",
    label: "Поиск по пользователям...",
    paramName: "q",
  },
  {
    type: "select",
    key: "is_active",
    label: "Статус",
    allLabel: "Все статусы",
    options: STATUS_OPTIONS,
    mapToApi: {
      "true": true,
      "false": false,
    },
  },
  {
    type: "select",
    key: "role",
    label: "Роль",
    allLabel: "Все роли",
    options: ROLE_OPTIONS,
  },
  {
    type: "dict-select",
    key: "department",
    label: "Отдел",
    allLabel: "Все отделы",
  },
];

export default function AdminUsersPage() {
  const { data: departments = [] } = useGetDepartmentsQuery();
  const departmentOptions = useMemo(
    () => departments.map((d) => ({ label: d.name, value: String(d.id) })),
    [departments],
  );

  const {
    filterValues,
    setFilter,
    searchQuery,
    setSearchQuery,
    debouncedSearch,
    filtersKey,
  } = useTableFilters(USER_FILTERS);

  // department_id — единственный поддерживаемый бэком фильтр,
  // остальное (поиск, статус, роль) фильтруем на клиенте
  const apiParams = useMemo(() => {
    const params = buildApiParams(
      USER_FILTERS,
      filterValues,
      debouncedSearch
    );
    return {
      department_id: params.department ? Number(params.department) : undefined,
    };
  }, [debouncedSearch, filterValues]);

  const { data: allUsers = [], isLoading } = useGetAllUsersQuery(apiParams);

  const users = useMemo(() => {
    const query = debouncedSearch.trim().toLowerCase();
    return allUsers.filter((user: AuthUser) => {
      // Поиск
      if (query) {
        const matches =
          user.full_name.toLowerCase().includes(query) ||
          user.email.toLowerCase().includes(query);
        if (!matches) return false;
      }
      // Статус
      const statusFilter = filterValues["is_active"];
      if (statusFilter) {
        const statusValue = statusFilter === "true";
        if (user.is_active !== statusValue) return false;
      }
      // Роль
      const roleFilter = filterValues["role"];
      if (roleFilter && user.role !== roleFilter) return false;
      return true;
    });
  }, [allUsers, debouncedSearch, filterValues]);

  return (
    <div className="flex flex-1 flex-col p-8">
      <TitlePage
        title="Пользователи"
        text="Отделы и доступ сотрудников к рабочим данным Kodik+."
      />

      <UserTable
        users={users}
        isLoading={isLoading}
        pageSize={PAGE_SIZE}
        filtersKey={filtersKey}
        configs={USER_FILTERS}
        filterValues={filterValues}
        onFilterChange={setFilter}
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        dateFrom=""
        dateTo=""
        onDateFromChange={() => {}}
        onDateToChange={() => {}}
        dictOptions={{ department: departmentOptions }}
      />
    </div>
  );
}
