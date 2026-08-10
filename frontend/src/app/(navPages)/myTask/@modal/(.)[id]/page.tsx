"use client";

import { useParams, useRouter } from "next/navigation";
import { CardTask } from "@/components/cards/CardTask";

export default function MyTaskModalPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = Number(params.id);

  return (
    <CardTask
      taskId={Number.isFinite(id) ? id : null}
      isOpen
      onClose={() => router.back()}
      onOpenIncident={(incidentId) => router.push(`/incidents/${incidentId}`)}
    />
  );
}
