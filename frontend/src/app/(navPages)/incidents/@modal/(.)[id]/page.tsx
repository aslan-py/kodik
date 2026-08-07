"use client";

import { useParams, useRouter } from "next/navigation";
import { useGetShowcaseByIdQuery } from "@/api/showcaseApi";
import { CardIncident } from "@/components/cards/CardIncident/CardIncident";

export default function IncidentModalPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = Number(params.id);

  const { data: incident, isLoading } = useGetShowcaseByIdQuery(id, {
    skip: !Number.isFinite(id),
  });

  if (isLoading) {
    return null;
  }

  return (
    <CardIncident
      incident={incident ?? null}
      isOpen
      onClose={() => router.back()}
    />
  );
}
