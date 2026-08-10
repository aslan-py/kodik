// @/hooks/useFilteredTasks.ts
import { useMemo, useState } from "react";
import { ActionItem } from "@/api/actionApi";
import { statusLabel } from "@/helpers/status";
import { useDepartmentsMap } from "./useDepartamentName";

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

export function useFilteredTasks(tasks: ActionItem[]) {
  const departmentsMap = useDepartmentsMap();

  const [statusFilter, setStatusFilter] = useState("");
  const [departmentFilter, setDepartmentFilter] = useState("");
  const [createdAtFilter, setCreatedAtFilter] = useState("");
  const [updatedAtFilter, setUpdatedAtFilter] = useState("");
  const [deadlineFilter, setDeadlineFilter] = useState("");
  const [dateFrom, setDateFrom] = useState(defaultRange.from);
  const [dateTo, setDateTo] = useState(defaultRange.to);

  const statusOptions = useMemo(() => {
    const values = [...new Set(tasks.map((t) => t.status))];
    return values.map((v) => ({ label: statusLabel(v), value: v }));
  }, [tasks]);

  const departmentOptions = useMemo(() => {
    const ids = [...new Set(tasks.map((t) => t.department_id))];
    return ids.map((id) => ({
      label: departmentsMap.get(id) ?? String(id),
      value: String(id),
    }));
  }, [tasks, departmentsMap]);

  const startOfToday = new Date();
  startOfToday.setHours(0, 0, 0, 0);
  const startOfYesterday = new Date(startOfToday);
  startOfYesterday.setDate(startOfYesterday.getDate() - 1);
  const startOfWeek = new Date(startOfToday);
  startOfWeek.setDate(startOfWeek.getDate() - 7);
  const startOfMonth = new Date(startOfToday);
  startOfMonth.setDate(startOfMonth.getDate() - 30);

  const matchesDateOption = (value: string | null | undefined, option: string) => {
    if (!option || !value) return true;
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return true;
    switch (option) {
      case "today": return d >= startOfToday;
      case "yesterday": return d >= startOfYesterday && d < startOfToday;
      case "week": return d >= startOfWeek;
      case "month": return d >= startOfMonth;
      default: return true;
    }
  };

  const matchesDeadlineOption = (value: string | null | undefined, option: string) => {
    if (!option || !value) return true;
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return true;
    switch (option) {
      case "today": return d >= startOfToday && d < new Date(startOfToday.getTime() + 86400000);
      case "tomorrow":
        return d >= new Date(startOfToday.getTime() + 86400000) && d < new Date(startOfToday.getTime() + 2 * 86400000);
      case "week": return d >= startOfToday && d < new Date(startOfToday.getTime() + 7 * 86400000);
      case "month": return d >= startOfToday && d < new Date(startOfToday.getTime() + 30 * 86400000);
      case "overdue": return d < startOfToday;
      default: return true;
    }
  };

  const filteredTasks = useMemo(() => {
    const fromBound = dateFrom ? new Date(dateFrom + "T00:00:00") : null;
    const toBound = dateTo ? new Date(new Date(dateTo + "T00:00:00").getTime() + 86400000) : null;

    const filtered = tasks.filter((item) => {
      const itemDate = item.created_at ? new Date(item.created_at) : null;
      return (
        (!statusFilter || item.status === statusFilter) &&
        (!departmentFilter || String(item.department_id) === departmentFilter) &&
        matchesDateOption(item.created_at, createdAtFilter) &&
        matchesDateOption(item.updated_at, updatedAtFilter) &&
        matchesDeadlineOption(item.deadline, deadlineFilter) &&
        (!fromBound || !itemDate || itemDate >= fromBound) &&
        (!toBound || !itemDate || itemDate <= toBound)
      );
    });

    return [...filtered].sort((a, b) => {
      if (!a.deadline && !b.deadline) return 0;
      if (!a.deadline) return 1;
      if (!b.deadline) return -1;
      return new Date(a.deadline).getTime() - new Date(b.deadline).getTime();
    });
  }, [tasks, statusFilter, departmentFilter, createdAtFilter, updatedAtFilter, deadlineFilter, dateFrom, dateTo]);

  return {
    filteredTasks,
    statusOptions, departmentOptions,
    statusFilter, setStatusFilter,
    departmentFilter, setDepartmentFilter,
    createdAtFilter, setCreatedAtFilter,
    updatedAtFilter, setUpdatedAtFilter,
    deadlineFilter, setDeadlineFilter,
    dateFrom, setDateFrom, dateTo, setDateTo,
  };
}