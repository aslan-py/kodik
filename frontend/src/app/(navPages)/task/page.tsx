"use client";

import { useRouter } from "next/navigation";
import TaskTable from "@/components/tables/TaskTable";
import TitlePage from "@/components/layout/TitlePage";
import { useGetActionItemsQuery } from "@/api/actionApi";

export default function TaskPage() {
  const router = useRouter();
  const { data: tasks = [] } = useGetActionItemsQuery();

  const totalTasks = tasks.length;
  const inProgressTasks = tasks.filter((t) => t.status === "in_progress").length;

  const metricsEvent = [
    { label: "всего задач", value: totalTasks },
    { label: "в работе", value: inProgressTasks },
  ];

  return (
    <div className="flex flex-1 flex-col p-8">
      <TitlePage
        title="Задачи"
        text="Контроль исполнения поручений, созданных на основе обнаруженных событий конкурентной разведки."
        metrics={metricsEvent}
      />

      <TaskTable onOpen={(task) => router.push(`/task/${task.id}`)} />
    </div>
  );
}
