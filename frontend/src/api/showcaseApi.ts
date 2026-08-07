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
  title?: string;
  category?: string;
  priority?: string;
  region?: string;
  competitor?: string;
  department?: string;
  published_from?: string;
  published_to?: string;
};
type UpdateShowcaseRequest = {
  priority?: string;
  category_id?: number;
  tonality?: string;
  action?: string;
  deadline?: string; // ISO-дата
  department_id?: number;
  comment?: string;
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
    }),
    getShowcaseById: builder.query<Showcase, number>({
      query: (id) => `/showcase/${id}`,
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
    }),
  }),
});

export const { useGetShowcasesQuery, useGetShowcaseByIdQuery } = showcaseApi;
