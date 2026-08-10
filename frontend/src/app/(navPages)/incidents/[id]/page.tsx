"use client";

import { useParams, useRouter } from "next/navigation";
import { IncidentWithTask } from "@/components/cards/IncidentWithTask/IncidentWithTask";
import IncidentsPage from "../page";

export default function IncidentDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = Number(params.id);

  return (
    <>
      <IncidentsPage />
      <IncidentWithTask incidentId={id} onClose={() => router.push("/incidents")} />
    </>
  );
}