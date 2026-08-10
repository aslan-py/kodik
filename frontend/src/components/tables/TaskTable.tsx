"use client";

import { Table, TableColumn } from "@/components/ui/Table/Table";
import { ActionItem } from "@/api/actionApi";
import { useFilteredTasks } from "@/hooks/useFilteredTask";
import { FilterKey, TaskFilters } from "../filters/TaskFilters/TaskFilters";

type TaskTableProps = {
  tasks: ActionItem[];
  columns: TableColumn<ActionItem>[];
  onOpen?: (task: ActionItem) => void;
  visibleFilters?: FilterKey[];
};

const defaultVisibleFilters: FilterKey[] = [
  "status",
  "department",
  "createdAt",
  "updatedAt",
  "deadline",
  "period",
];

export default function TaskTable({
  tasks,
  columns,
  onOpen,
  visibleFilters = defaultVisibleFilters,
}: TaskTableProps) {
  const {
    filteredTasks,
    statusOptions,
    departmentOptions,
    statusFilter,
    setStatusFilter,
    departmentFilter,
    setDepartmentFilter,
    createdAtFilter,
    setCreatedAtFilter,
    updatedAtFilter,
    setUpdatedAtFilter,
    deadlineFilter,
    setDeadlineFilter,
    dateFrom,
    setDateFrom,
    dateTo,
    setDateTo,
  } = useFilteredTasks(tasks);

  const show = (key: FilterKey) => visibleFilters.includes(key);

  return (
    <>
      <TaskFilters
        statusFilter={statusFilter}
        onStatusChange={show("status") ? setStatusFilter : undefined}
        statusOptions={statusOptions}
        departmentFilter={departmentFilter}
        onDepartmentChange={
          show("department") ? setDepartmentFilter : undefined
        }
        departmentOptions={departmentOptions}
        createdAtFilter={createdAtFilter}
        onCreatedAtChange={show("createdAt") ? setCreatedAtFilter : undefined}
        updatedAtFilter={updatedAtFilter}
        onUpdatedAtChange={show("updatedAt") ? setUpdatedAtFilter : undefined}
        deadlineFilter={deadlineFilter}
        onDeadlineChange={show("deadline") ? setDeadlineFilter : undefined}
        dateFrom={dateFrom}
        dateTo={dateTo}
        onDateFromChange={show("period") ? setDateFrom : undefined}
        onDateToChange={show("period") ? setDateTo : undefined}
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
