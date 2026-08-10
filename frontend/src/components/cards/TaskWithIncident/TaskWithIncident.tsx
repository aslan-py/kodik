"use client";

import { useState } from "react";
import { useGetShowcaseByIdQuery } from "@/api/showcaseApi";
import { CardTask } from "@/components/cards/CardTask";
import { CardIncident } from "@/components/cards/CardIncident/CardIncident";

export function TaskWithIncident({
  taskId,
  onClose,
}: {
  taskId: number | null;
  onClose: () => void;
}) {
  const [openIncidentId, setOpenIncidentId] = useState<number | null>(null);

  const { data: incident } = useGetShowcaseByIdQuery(openIncidentId ?? 0, {
    skip: !openIncidentId,
  });

  return (
    <>
      <CardTask
        taskId={taskId}
        isOpen
        onClose={onClose}
        onOpenIncident={(incidentId) => setOpenIncidentId(incidentId)}
      />

      <CardIncident
        incident={incident ?? null}
        isOpen={openIncidentId !== null}
        onClose={() => setOpenIncidentId(null)}
      />
    </>
  );
}