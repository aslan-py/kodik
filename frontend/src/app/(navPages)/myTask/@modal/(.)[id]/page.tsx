"use client";

import { useParams, useRouter } from "next/navigation";
import { CardTask } from "@/components/cards/CardTask";
import { TaskWithIncident } from "@/components/cards/TaskWithIncident/TaskWithIncident";

export default function MyTaskModalPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = Number(params.id);

  return (
    <TaskWithIncident
          taskId={Number.isFinite(id) ? id : null}
          onClose={() => router.back()}
        />
  );
}
