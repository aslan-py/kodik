"use client";

import { useState } from "react";
import IncidentTable from "@/components/tables/IncidentTable";
import { CardIncident } from "@/components/cards/CardIncident/CardIncident";
import TitlePage from "@/components/layout/TitlePage";
import type { IncidentItem } from "@/types/types";

export default function IncidentsPage() {
  const [selectedIncident, setSelectedIncident] = useState<IncidentItem | null>(null);

  const metricsEvent = [
    { label: "событий", value: 248 },
    { label: "приоритет П1", value: 28 },
    { label: "приоритет П2", value: 120 },
  ];

  return (
    <div className="flex flex-1 flex-col p-8">
      <TitlePage
        title="События"
        text="Мониторинг событий и новостей по рынку и конкурентам."
        dataToday
        metrics={metricsEvent}
      />

      <div>
        <IncidentTable onOpen={setSelectedIncident} />
      </div>

      <CardIncident
        incident={selectedIncident}
        // isOpen={!!selectedIncident}
        isOpen={true}
        onClose={() => setSelectedIncident(null)}
      />
    </div>
  );
}
