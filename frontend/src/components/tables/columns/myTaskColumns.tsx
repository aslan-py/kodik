// @/components/tables/columns/myTaskColumns.tsx — тот же принцип, но без колонки "Отдел",

import { ActionItem } from "@/api/actionApi";
import { DeadlineBadge } from "@/components/features/DeadLineBadge";
import { TableColumn } from "@/components/ui/Table";
import { formatDateWithTime } from "@/helpers/date";
import { statusClass, statusLabel } from "@/helpers/status";
import { useMemo } from "react";

// например, и без showcase, зато с колонкой "Ожидаемый результат"
export function useMyTaskColumns(): TableColumn<ActionItem>[] {
  return useMemo<TableColumn<ActionItem>[]>(() => [
    {
      key: "title",
      header: "Задача",
      render: (item) => (
        <span className="block text-(--color-ink) font-medium max-w-80 truncate">{item.task}</span>
      ),
    },
    {
      key: "expected_result",
      header: "Результат",
      render: (item) => <span className="block text-(--color-ink)">{item.expected_result}</span>,
    },
    {
      key: "assigned_user_id",
      header: "Исполнитель",
      render: (item) => <span className="block text-(--color-ink)">{item.assigned_user_id}</span>,
    },
    {
      key: "status",
      header: "Статус",
      render: (item) => <span className={statusClass(item.status)}>{statusLabel(item.status)}</span>,
    },
    {
      key: "deadline",
      header: "Срок",
      render: (item) => <DeadlineBadge deadline={item.deadline} isDone={item.status === "done"} />,
    },
    {
      key: "created_at",
      header: "Создана",
      render: (item) => (
        <span className="block whitespace-nowrap text-(--color-ink)">{formatDateWithTime(item.created_at)}</span>
      ),
    },
  ], []);
}