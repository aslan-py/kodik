import type { IncidentItem } from "@/types/types";
import { mockIncidents } from "@/data/mockIncidents";

export async function fetchIncidents(): Promise<IncidentItem[]> {
    return new Promise((resolve) => {
        setTimeout(() => {
            resolve(mockIncidents);
        }, 3000);
    });
}