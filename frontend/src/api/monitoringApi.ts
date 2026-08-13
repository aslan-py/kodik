import { baseApi } from "./baseApi";

export type Trigger = {
  id: number;
  keyword: string;
  is_active: boolean;
};

export type TriggerQuery = {
  q?: string;
  is_active?: boolean;
  limit?: number;
  offset?: number;
};

type CreateTrigger = {
  keyword: string;
};

type UpdateTrigger = {
  keyword: string;
};

export type Competitor = {
  id: number;
  name: string;
  inn: string;
  is_active: boolean;
};

export type CompetitorQuery = {
  q?: string;
  is_active?: boolean;
  limit?: number;
  offset?: number;
};

type CreateCompetitor = {
  name: string;
  inn: string;
};

type UpdateCompetitor = {
  name: string;
  inn: string;
};

export const monitoringApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    // триггеры
    getTriggers: builder.query<Trigger[], TriggerQuery>({
      query: (params) => ({
        url: "/triggers",
        method: "GET",
        params,
      }),
      providesTags: ["Trigger"],
    }),
    addTrigger: builder.mutation<Trigger, CreateTrigger>({
      query: (body) => ({
        url: `/triggers`,
        method: "POST",
        body,
      }),
      invalidatesTags: ["Trigger"],
    }),
    getTriggerById: builder.query<Trigger, number>({
      query: (id) => `/triggers/${id}`,
      providesTags: ["Trigger"],
    }),
    editTrigger: builder.mutation<
      Trigger,
      { id: number; body: UpdateTrigger }
    >({
      query: ({ id, body }) => ({
        url: `/triggers/${id}`,
        method: "PATCH",
        body,
      }),
      invalidatesTags: ["Trigger"],
    }),
    deleteTrigger: builder.mutation<Trigger, number>({
      query: (id) => ({
        url: `/triggers/${id}`,
        method: "DELETE",
      }),
      invalidatesTags: ["Trigger"],
    }),

    // конкуренты
    getCompetitors: builder.query<Competitor[], CompetitorQuery>({
      query: (params) => ({
        url: "/competitors",
        method: "GET",
        params,
      }),
      providesTags: ["Competitor"],
    }),
    addCompetitor: builder.mutation<Competitor, CreateCompetitor>({
      query: (body) => ({
        url: `/competitors`,
        method: "POST",
        body,
      }),
      invalidatesTags: ["Competitor"],
    }),
    getCompetitorById: builder.query<Competitor, number>({
      query: (id) => `/competitors/${id}`,
      providesTags: ["Competitor"],
    }),
    editCompetitor: builder.mutation<
      Competitor,
      { id: number; body: UpdateCompetitor }
    >({
      query: ({ id, body }) => ({
        url: `/competitors/${id}`,
        method: "PATCH",
        body,
      }),
      invalidatesTags: ["Competitor"],
    }),
    deleteCompetitor: builder.mutation<Competitor, number>({
      query: (id) => ({
        url: `/competitors/${id}`,
        method: "DELETE",
      }),
      invalidatesTags: ["Competitor"],
    }),
  }),
});

export const {
  useGetTriggersQuery,
  useAddTriggerMutation,
  useGetTriggerByIdQuery,
  useEditTriggerMutation,
  useDeleteTriggerMutation,
  useGetCompetitorsQuery,
  useAddCompetitorMutation,
  useGetCompetitorByIdQuery,
  useEditCompetitorMutation,
  useDeleteCompetitorMutation,
} = monitoringApi;