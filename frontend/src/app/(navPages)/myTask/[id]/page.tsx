// src/app/(navPages)/myTask/[id]/page.tsx
"use client";

import { useParams, useRouter } from "next/navigation";
import { CardTask } from "@/components/cards/CardTask";
import MyTaskPage from "../page";

export default function MyTaskDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = Number(params.id);

  return (
    <>
      <MyTaskPage />
      <CardTask
        taskId={Number.isFinite(id) ? id : null}
        isOpen
        onClose={() => router.push("/myTask")}
        onOpenIncident={(incidentId) => router.push(`/incidents/${incidentId}`)}
      />
    </>
  );
}
