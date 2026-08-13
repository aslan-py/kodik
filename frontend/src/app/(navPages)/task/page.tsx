"use client";

import { useRouter } from "next/navigation";
import { useMemo } from "react";
import TaskTable from "@/components/tables/TaskTable";
import { useAllTaskColumns } from "@/components/tables/columns/allTaskColumns";
import TitlePage from "@/components/layout/TitlePage";
import { useGetActionItemsQuery, GetActionItemsParams } from "@/api/actionApi";
import { useTableFilters } from "@/hooks/useTableFilters";
import { FilterConfig } from "@/hooks/filters/types";
import { TASK_STATUS_OPTIONS } from "@/types/types";
import { useGetDepartmentsQuery } from "@/api/adminSourceApi";

// 1. Описываем конфигурацию фильтров
const TASK_FILTERS: FilterConfig[] = [
  {
    type: "search",
    key: "search",
    label: "Поиск...",
    paramName: "task",
  },
  {
    type: "select",
    key: "status",
    label: "Статус",
    allLabel: "Все статусы",
    options: TASK_STATUS_OPTIONS,
  },
  {
    type: "dict-select",
    key: "department",
    label: "Отдел",
    allLabel: "Все отделы",
  },
];

export default function TaskPage() {
  const router = useRouter();
  const columns = useAllTaskColumns();

  // 2. Загружаем опции для dict-select фильтров
  const { data: departments = [] } = useGetDepartmentsQuery();
  const departmentOptions = useMemo(
    () => departments.map((d) => ({ label: d.name, value: String(d.id) })),
    [departments],
  );

  // 3. Хук фильтров
  const {
    filterValues,
    setFilter,
    searchQuery,
    setSearchQuery,
    debouncedSearch,
    filtersKey,
  } = useTableFilters(TASK_FILTERS);

  // 4. Собираем параметры для API
  const apiParams = useMemo<GetActionItemsParams>(() => {
    const params: GetActionItemsParams = {};

    // Поиск
    if (debouncedSearch.trim()) {
      params.task = debouncedSearch.trim();
    }

    // Селекты
    if (filterValues.status) params.status = filterValues.status;
    if (filterValues.department) params.department_id = Number(filterValues.department);

    return params;
  }, [debouncedSearch, filterValues]);

  // 5. Загружаем данные
  const { data: tasks = [], isLoading } = useGetActionItemsQuery(apiParams);

  const metricsEvent = [
    { label: "всего задач", value: tasks.length },
    {
      label: "в работе",
      value: tasks.filter((t) => t.status === "in_progress").length,
    },
  ];

  if (isLoading)
    return (
      <div className="text-sm text-(--color-muted) py-8">Загрузка задач...</div>
    );

  return (
    <div className="flex flex-1 flex-col p-8">
      <TitlePage
        title="Задачи"
        text="Контроль исполнения поручений, созданных на основе обнаруженных событий конкурентной разведки."
        metrics={metricsEvent}
      />

      <TaskTable
        tasks={tasks}
        columns={columns}
        onOpen={(task) => router.push(`/task/${task.id}`)}
        configs={TASK_FILTERS}
        filterValues={filterValues}
        onFilterChange={setFilter}
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        dictOptions={{ department: departmentOptions }}
        filtersKey={filtersKey}
      />
    </div>
  );
}
