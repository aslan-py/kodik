"use client";

import { useRouter } from "next/navigation";
import TaskTable from "@/components/tables/TaskTable";
import { useAllTaskColumns } from "@/components/tables/columns/allTaskColumns";
import TitlePage from "@/components/layout/TitlePage";
import { useGetActionItemsQuery } from "@/api/actionApi";

export default function TaskPage() {
  const router = useRouter();
  const { data: tasks = [], isLoading } = useGetActionItemsQuery();
  const columns = useAllTaskColumns();

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
        visibleFilters={["status", "department", "deadline", "period"]}
      />
    </div>
  );
}
