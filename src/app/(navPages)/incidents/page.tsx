"use client";

import { useState, useCallback } from "react";
import IncidentTable from "@/components/tables/IncidentTable";
import TitlePage from "@/components/layout/TitlePage";

import type { IncidentItem } from "@/types/types";
import { CardTask } from "@/components/cards/CardTask/CardTask";
import { CardIncident } from "@/components/cards/CardIncident/CardIncident";
import { mockIncidents } from "@/data/mockIncidents";

export default function IncidentsPage() {
  const [selectedIncident, setSelectedIncident] = useState<IncidentItem | null>(null);
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [linkedIncidentTitle, setLinkedIncidentTitle] = useState<string | null>(null);

  const metricsEvent = [
    { label: "событий", value: 248 },
    { label: "приоритет П1", value: 28 },
    { label: "приоритет П2", value: 120 },
  ];

  const linkedIncident = linkedIncidentTitle
    ? mockIncidents.find((i) => i.incident === linkedIncidentTitle) ?? null
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
        title="События"
        text="Мониторинг событий и новостей по рынку и конкурентам."
        dataToday
        metrics={metricsEvent}
      />

        <IncidentTable onOpen={setSelectedIncident} />

      {/* Карточка инцидента из таблицы */}
      <CardIncident
        incident={selectedIncident}
        isOpen={!!selectedIncident && !selectedTaskId && !linkedIncidentTitle}
        onClose={() => setSelectedIncident(null)}
        onOpenTask={handleOpenTask}
        onTaskCreated={(taskId) => {
          if (selectedIncident) {
            setSelectedIncident({ ...selectedIncident, taskId });
          }
        }}
      />

      {/* Карточка задачи */}
      <CardTask
        taskId={selectedTaskId}
        isOpen={!!selectedTaskId && !linkedIncidentTitle}
        onClose={() => setSelectedTaskId(null)}
        onOpenIncident={handleOpenLinkedIncident}
      />

      {/* Карточка связанного события (открыта из задачи) */}
      <CardIncident
        incident={linkedIncident}
        isOpen={!!linkedIncidentTitle}
        onClose={() => setLinkedIncidentTitle(null)}
        onOpenTask={(taskId) => {
          setLinkedIncidentTitle(null);
          setSelectedTaskId(taskId);
        }}
      />
    </div>
  );
}