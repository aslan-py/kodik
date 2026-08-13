// src/app/(navPages)/task/[id]/page.tsx
"use client";

import { useParams, useRouter } from "next/navigation";
import { TaskWithIncident } from "@/components/cards/TaskWithIncident/TaskWithIncident";
import TaskPage from "../page";

export default function TaskDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = Number(params.id);

  return (
    <>
      <TaskPage />
      <TaskWithIncident
        taskId={Number.isFinite(id) ? id : null}
        onClose={() => router.push("/task")}
      />
    </>
  );
}