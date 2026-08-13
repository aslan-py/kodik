"use client";

import { TableColumn } from "@/components/ui/Table/Table";

import { ROLE_LABELS } from "@/constants/roles";
import { useDepartmentsMap } from "@/hooks/useDepartamentName";
import { AuthUser } from "@/store/authSlice";

export function useUserColumns(
  onEdit: (user: AuthUser) => void,
): TableColumn<AuthUser>[] {
   const departmentsMap = useDepartmentsMap();

  return [
    {
      key: "full_name",
      header: "Пользователь",
      render: (user) => (
        <div className="flex flex-col">
          <span className="font-medium">{user.full_name}</span>
          <span className="text-xs text-(--color-muted)">{user.email}</span>
        </div>
      ),
    },
    {
      key: "department",
      header: "Отдел",
      render: (user) =>
        user.department_id != null
          ? (departmentsMap.get(user.department_id) ?? "—")
          : "—",
    },
    {
      key: "telegram_username",
      header: "Telegram",
      render: (user) =>
        user.telegram_id ? `${user.telegram_id}` : "—",
    },
    {
      key: "is_active",
      header: "Статус",
      render: (user) => (
        <span
          className={
            user.is_active ? "text-(--color-success)" : "text-(--color-muted)"
          }
        >
          {user.is_active ? "Активен" : "Неактивен"}
        </span>
      ),
    },
    {
      key: "role",
      header: "Роль",
      render: (user) => ROLE_LABELS[user.role] ?? user.role,
    },
    {
      key: "actions",
      header: "",
      className: "text-right",
      render: (user) => (
        <button
          onClick={(e) => {
            e.stopPropagation();
            onEdit(user);
          }}
          className="text-sm text-(--color-primary) hover:underline"
        >
          Редактировать
        </button>
      ),
    },
  ];
}