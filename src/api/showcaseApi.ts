import { baseApi } from "./baseApi";
export interface ShowcaseResponse {
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
}

export interface PaginatedResponse<T> {
  data: T[];
  limit: number;
  offset: number;
  // total: number;
  // page: number;
  // totalPages: number;
}

export const showcaseApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    getShowcase: builder.query<
      PaginatedResponse<ShowcaseResponse>,
      { offset: number; limit: number }
    >({
      query: ({ offset, limit }) => ({
        url: "/showcase",
        params: {
          offset,
          limit,
        },
      }),
    }),
    getShowcaseId: builder.query<ShowcaseResponse, { showcase_id: number }>({
      query: ({ showcase_id }) => ({
        url: `/showcase/${showcase_id}`,
        params: {
          showcase_id,
        },
      }),
    }),
    editShowcaseId: builder.mutation<ShowcaseResponse,{ data: ShowcaseResponse }>({
      query: ({ data }) => ({
        url: `/showcase/${data.id}`,
        method: "PATCH",
        body: data,
      }),
      invalidatesTags: (_result, _err, { data }) => [
        "Showcases",
        { type: "Showcases", id: data.id },
      ],
    }),
  }),
});

export const { useGetShowcaseQuery, useGetShowcaseIdQuery, useEditShowcaseIdMutation } = showcaseApi;
