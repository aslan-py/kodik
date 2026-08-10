"use client";

import { useRouter } from "next/navigation";
import TaskTable from "@/components/tables/TaskTable";
import { useMyTaskColumns } from "@/components/tables/columns/myTaskColumns";
import TitlePage from "@/components/layout/TitlePage";
import { useGetActionItemsQuery } from "@/api/actionApi";

export default function MyTaskPage() {
  const router = useRouter();
  const { data: tasks = [], isLoading } = useGetActionItemsQuery(); // ⚠️ см. ниже
  const columns = useMyTaskColumns();
  const totalTasks = tasks.length;
  const inProgressTasks = tasks.filter(
    (t) => t.status === "in_progress",
  ).length;

  const metricsEvent = [
    // TODO
    { label: "всего задач", value: totalTasks },
    { label: "в работе", value: inProgressTasks },
  ];
  if (isLoading)
    return (
      <div className="text-sm text-(--color-muted) py-8">Загрузка задач...</div>
    );

  return (
    <div className="flex flex-1 flex-col p-8">
      <TitlePage
        title="Мои задачи"
        text="Контроль исполнения поручений, созданных на основе обнаруженных событий конкурентной разведки."
        metrics={metricsEvent}
      />

      <TaskTable
        tasks={tasks}
        columns={columns}
        onOpen={(task) => router.push(`/myTask/${task.id}`)}
        visibleFilters={["status", "createdAt", "deadline", "period"]}
      />
    </div>
  );
}
