// src/app/(navPages)/task/@modal/(.)[id]/page.tsx
"use client";

import { useParams, useRouter } from "next/navigation";
import { TaskWithIncident } from "@/components/cards/TaskWithIncident/TaskWithIncident";

export default function TaskModalPage() {
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