// src/app/(navPages)/incidents/_components/IncidentsListContent.tsx
"use client";

import { useRouter } from "next/navigation";
import IncidentTable from "@/components/tables/IncidentTable";
import TitlePage from "@/components/layout/TitlePage";

const metricsEvent = [
  { label: "событий", value: 248 },
  { label: "приоритет П1", value: 28 },
  { label: "приоритет П2", value: 120 },
];

export function IncidentsListContent() {
  const router = useRouter();

  return (
    <div className="flex flex-1 flex-col p-8">
      <TitlePage
        title="События"
        text="Мониторинг событий и новостей по рынку и конкурентам."
        dataToday
        lastUpdated="2026-07-28T16:22:00"
        metrics={metricsEvent}
      />
      <IncidentTable onOpen={(incident) => router.push(`/incidents/${incident.id}`)} />
    </div>
  );
}