"use client";

import { useRouter } from "next/navigation";
import { CardTask } from "@/components/cards/CardTask";

export function TaskDetail({
  taskId,
  onClose,
}: {
  taskId: number | null;
  onClose: () => void;
}) {
  const router = useRouter();

  return (
    <CardTask
      taskId={taskId}
      isOpen
      onClose={onClose}
      onOpenIncident={(incidentId) => router.push(`/incidents/${incidentId}`)}
    />
  );
}