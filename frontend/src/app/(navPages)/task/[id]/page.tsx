// src/app/(navPages)/task/[id]/page.tsx
"use client";

import { useParams, useRouter } from "next/navigation";
import { CardTask } from "@/components/cards/CardTask";
import TaskPage from "../page";

export default function TaskDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = Number(params.id);

  return (
    <>
      <TaskPage />
      <CardTask
        taskId={Number.isFinite(id) ? id : null}
        isOpen
        onClose={() => router.push("/task")}
        onOpenIncident={(incidentId) => router.push(`/incidents/${incidentId}`)}
      />
    </>
  );
}
