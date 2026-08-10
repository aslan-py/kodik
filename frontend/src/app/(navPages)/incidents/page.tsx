// src/app/(navPages)/incidents/page.tsx
"use client";

import { useRouter } from "next/navigation";
import IncidentTable from "@/components/tables/IncidentTable";
import { useIncidentColumns } from "@/components/tables/columns/incidentColumns";
import TitlePage from "@/components/layout/TitlePage";

const metricsEvent = [
  { label: "событий", value: 248 },
  { label: "приоритет П1", value: 28 },
  { label: "приоритет П2", value: 120 },
];

export default function IncidentsPage() {
  const router = useRouter();
  const columns = useIncidentColumns();
  // TODO lastUpdated="2026-07-28T16:22:00"

  return (
    <div className="flex flex-1 flex-col p-8">
      <TitlePage
        title="События"
        text="Мониторинг событий и новостей по рынку и конкурентам."
        dataToday
        // lastUpdated="2026-07-28T16:22:00"
        metrics={metricsEvent}
      />
      <IncidentTable
        columns={columns}
        onOpen={(incident) => router.push(`/incidents/${incident.id}`)}
      />
    </div>
  );
}