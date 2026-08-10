"use client";

import { useParams, useRouter } from "next/navigation";
import { IncidentWithTask } from "@/components/cards/IncidentWithTask/IncidentWithTask";

export default function IncidentModalPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = Number(params.id);

  return <IncidentWithTask incidentId={id} onClose={() => router.back()} />;
}