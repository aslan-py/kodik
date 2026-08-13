import { baseApi } from "./baseApi";

export type Showcase = {
  id: number;
  categorized_event_id: number;
  raw_item_id: number;
  published_at: string;
  title: string;
  media: string;
  region: string;
  macro_region: string;
  latitude: number;
  longitude: number;
  competitor: string;
  source_url: string;
  priority: string;
  category: string;
  tonality: string;
  media_index: string;
  action: string;
  deadline: string;
  department: string;
  comment: string;
  updated_at: string;
  alerted_at: string;
};

export type GetShowcasesParams = {
  limit?: number;
  offset?: number;
  title?: string | null;
  category?: string | null;
  priority?: string | null;
  region?: string | null;
  competitor?: string | null;
  department?: string | null;
  published_from?: string | null;
  published_to?: string | null;
};
// PATCH
export type PriorityLevel = "p1" | "p2" | "p3" | "p4";
export type Tonality =
  | "positive"
  | "neutral"
  | "negative"
  | "alarming"
  | "irrelevant";

export type UpdateShowcaseRequest = {
  priority?: PriorityLevel | null;
  category_id?: number | null;
  tonality?: Tonality | null;
  action?: string | null;
  deadline?: string | null; // ISO-дата
  department_id?: number | null;
  comment?: string | null;
};

export const showcaseApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    getShowcases: builder.query<Showcase[], GetShowcasesParams | void>({
      query: (params) => {
        const sp = new URLSearchParams();
        if (params?.limit != null) sp.set("limit", String(params.limit));
        if (params?.offset != null) sp.set("offset", String(params.offset));
        if (params?.title) sp.set("title", params.title);
        if (params?.region) sp.set("region", params.region);
        if (params?.competitor) sp.set("competitor", params.competitor);
        if (params?.category) sp.set("category", params.category);
        if (params?.priority) sp.set("priority", params.priority);
        if (params?.department) sp.set("department", params.department);
        if (params?.published_from)
          sp.set("published_from", params.published_from);
        if (params?.published_to) sp.set("published_to", params.published_to);
        const qs = sp.toString();
        return qs ? `/showcase?${qs}` : "/showcase";
      },
      providesTags: (result) =>
        result
          ? [
              ...result.map((item) => ({ type: "Showcases" as const, id: item.id })),
              { type: "Showcases" as const, id: "LIST" },
            ]
          : [{ type: "Showcases" as const, id: "LIST" }],
    }),
    getShowcaseById: builder.query<Showcase, number>({
      query: (id) => `/showcase/${id}`,
      providesTags: (_result, _error, id) => [{ type: "Showcases", id }],
    }),
    updateShowcase: builder.mutation<
      Showcase,
      { id: number; body: UpdateShowcaseRequest }
    >({
      query: ({ id, body }) => ({
        url: `/showcase/${id}`,
        method: "PATCH",
        body,
      }),
      invalidatesTags: (_result, _error, { id }) => [
        { type: "Showcases", id },
        { type: "Showcases", id: "LIST" },
      ],
    }),
  }),
});

export const {
  useGetShowcasesQuery,
  useGetShowcaseByIdQuery,
  useUpdateShowcaseMutation,
} = showcaseApi;