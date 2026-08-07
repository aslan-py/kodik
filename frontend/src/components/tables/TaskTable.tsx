"use client";

import { useMemo, useState } from "react";
import { Table, TableColumn } from "@/components/ui/Table/Table";
import { TaskFilters } from "@/components/filters/TaskFilters";
import { useGetActionItemsQuery, ActionItem } from "@/api/actionApi";
import { formatDateWithTime } from "@/helpers/date";
import { statusLabel, statusClass } from "@/helpers/status";

/* ──────────────── Колонки ──────────────── */

function useTaskColumns(): TableColumn<ActionItem>[] {
  return useMemo<TableColumn<ActionItem>[]>(
    () => [
      {
        key: "title",
        header: "Задача",
        render: (item) => (
          <span className="block text-(--color-ink) font-medium max-w-80 truncate">
            {item.title}
          </span>
        ),
      },
      {
        key: "status",
        header: "Статус",
        render: (item) => (
          <span className={statusClass(item.status)}>
            {statusLabel(item.status)}
          </span>
        ),
      },
      {
        key: "deadline",
        header: "Срок",
        render: (item) => (
          <span className="block whitespace-nowrap text-(--color-ink)">
            {item.deadline ? formatDateWithTime(item.deadline) : "—"}
          </span>
        ),
      },
      {
        key: "created_at",
        header: "Создана",
        render: (item) => (
          <span className="block whitespace-nowrap text-(--color-ink)">
            {formatDateWithTime(item.created_at)}
          </span>
        ),
      },
    ],
    [],
  );
}

/* ──────────────── Дефолтный диапазон дат ──────────────── */

function getDefaultDateRange(): { from: string; to: string } {
  const now = new Date();
  const from = new Date(now);
  from.setDate(from.getDate() - 29);
  return {
    from: from.toISOString().slice(0, 10),
    to: now.toISOString().slice(0, 10),
  };
}

const defaultRange = getDefaultDateRange();

/* ──────────────── Компонент ──────────────── */

type TaskTableProps = {
  onOpen?: (task: ActionItem) => void;
};

export default function TaskTable({ onOpen }: TaskTableProps) {
  const { data: tasks = [], isLoading } = useGetActionItemsQuery();
  const [statusFilter, setStatusFilter] = useState("");
  const [dateFrom, setDateFrom] = useState(defaultRange.from);
  const [dateTo, setDateTo] = useState(defaultRange.to);
  const columns = useTaskColumns();

  const statusOptions = useMemo(() => {
    const values = [...new Set(tasks.map((t) => t.status))];
    return values.map((v) => ({ label: statusLabel(v), value: v }));
  }, [tasks]);

  const filteredTasks = useMemo(() => {
    // границы диапазона считаем один раз, а не на каждой итерации
    const fromBound = dateFrom ? new Date(dateFrom + "T00:00:00") : null;
    const toBound = dateTo
      ? new Date(new Date(dateTo + "T00:00:00").getTime() + 86400000)
      : null;

    return tasks.filter((item) => {
      const matchesStatus = !statusFilter || item.status === statusFilter;

      // задачи без дедлайна не участвуют в фильтрации по датам
      // и остаются в списке независимо от выбранного диапазона
      const itemDate = item.deadline ? new Date(item.deadline) : null;
      const matchesDateFrom =
        !fromBound || !itemDate || itemDate >= fromBound;
      const matchesDateTo = !toBound || !itemDate || itemDate <= toBound;

      return matchesStatus && matchesDateFrom && matchesDateTo;
    });
  }, [tasks, statusFilter, dateFrom, dateTo]);

  if (isLoading) {
    return (
      <div className="text-sm text-(--color-muted) py-8">
        Загрузка задач...
      </div>
    );
  }

  return (
    <>
      <TaskFilters
        statusFilter={statusFilter}
        onStatusChange={setStatusFilter}
        statusOptions={statusOptions}
        dateFrom={dateFrom}
        dateTo={dateTo}
        onDateFromChange={setDateFrom}
        onDateToChange={setDateTo}
      />
      <Table
        data={filteredTasks}
        columns={columns}
        pageSize={10}
        getRowKey={(item) => item.id}
        resetPaginationKey={`${statusFilter}-${dateFrom}-${dateTo}`}
        onRowClick={onOpen}
      />
    </>
  );
}