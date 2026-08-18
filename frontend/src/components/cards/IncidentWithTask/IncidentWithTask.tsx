"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useGetShowcaseByIdQuery } from "@/api/showcaseApi";
import { CardIncident } from "@/components/cards/CardIncident/CardIncident";
import { CardTask } from "@/components/cards/CardTask/CardTask";

export function IncidentWithTask({
  incidentId,
  onClose,
}: {
  incidentId: number;
  onClose: () => void;
}) {
  const [openTaskId, setOpenTaskId] = useState<number | null>(null);
  const router = useRouter();

  const { data: incident, isLoading } = useGetShowcaseByIdQuery(incidentId, {
    skip: !Number.isFinite(incidentId),
  });

  if (isLoading) return null;

  return (
    <>
      <CardIncident
        incident={incident ?? null}
        isOpen
        onClose={onClose}
        onOpenTask={(taskId) => setOpenTaskId(taskId)}
      />

      <CardTask
        taskId={openTaskId}
        isOpen={openTaskId !== null}
        onClose={() => setOpenTaskId(null)}
        onOpenIncident={(incidentId) => {
          setOpenTaskId(null);
          router.push(`/incidents/${incidentId}`);
        }}
      />
    </>
  );
}