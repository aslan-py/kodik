// src/app/(navPages)/incidents/[id]/page.tsx
"use client";

import { useParams, useRouter } from "next/navigation";
import { useGetShowcaseByIdQuery } from "@/api/showcaseApi";
import { CardIncident } from "@/components/cards/CardIncident/CardIncident";
import { IncidentsListContent } from "../_components/IncidentsListContent";

export default function IncidentDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = Number(params.id);

  const { data: incident, isLoading } = useGetShowcaseByIdQuery(id, {
    skip: !Number.isFinite(id),
  });

  return (
    <>
      <IncidentsListContent />
      {!isLoading && (
        <CardIncident
          incident={incident ?? null}
          isOpen
          onClose={() => router.push("/incidents")}
        />
      )}
    </>
  );
}