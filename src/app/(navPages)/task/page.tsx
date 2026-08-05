"use client";

import { useState, useCallback } from "react";
import IncidentTable from "@/components/tables/IncidentTable";
import TitlePage from "@/components/layout/TitlePage";

import type { IncidentItem } from "@/types/types";
import { CardTask } from "@/components/cards/CardTask/CardTask";
import { CardIncident } from "@/components/cards/CardIncident/CardIncident";
import { mockIncidents } from "@/data/mockIncidents";

export default function TaskPage() {
  const [selectedIncident, setSelectedIncident] = useState<IncidentItem | null>(
    null,
  );
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [linkedIncidentTitle, setLinkedIncidentTitle] = useState<string | null>(
    null,
  );

  const metricsEvent = [
    { label: "всего задач", value: 42 },
    { label: "всего задач", value: 18 },
    { label: "просрочено", value: 6 },
  ];

  const linkedIncident = linkedIncidentTitle
    ? (mockIncidents.find((i) => i.incident === linkedIncidentTitle) ?? null)
    : null;

  // const handleCloseAll = useCallback(() => {
  //   setSelectedIncident(null);
  //   setSelectedTaskId(null);
  //   setLinkedIncidentTitle(null);
  // }, []);

  const handleOpenTask = useCallback((taskId: string) => {
    setSelectedTaskId(taskId);
    setLinkedIncidentTitle(null);
  }, []);

  const handleOpenLinkedIncident = useCallback((incidentTitle: string) => {
    setLinkedIncidentTitle(incidentTitle);
    setSelectedTaskId(null);
  }, []);

  return (
    <div className="flex flex-1 flex-col p-8">
      <TitlePage
        title="Задачи"
        text="Контроль исполнения поручений, созданных на основе обнаруженных событий конкурентной разведки."
        metrics={metricsEvent}
      />

      <IncidentTable onOpen={setSelectedIncident} />

    </div>
  );
}
