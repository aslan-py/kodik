import { createApi } from "@reduxjs/toolkit/query/react";
import type { IncidentItem } from "@/types/types";
import { mockIncidents } from "@/data/mockIncidents";

export const incidentsApi = createApi({
    reducerPath: "incidentsApi",
    baseQuery: async () => ({ data: null }),
    tagTypes: ["Incidents"],
    endpoints: (builder) => ({
        getIncidents: builder.query<IncidentItem[], void>({
            queryFn: async () => {
                await new Promise((resolve) => setTimeout(resolve, 3000));
                return { data: mockIncidents };
            },
            providesTags: ["Incidents"],
        }),
    }),
});

export const { useGetIncidentsQuery } = incidentsApi;