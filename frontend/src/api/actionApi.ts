// src/api/actionApi.ts
import { baseApi } from "./baseApi";

export type ActionItem = {
  id: number;
  showcase_event_id: number;
  task: string;
  department_id: number;
  assigned_user_id?: number | null;
  deadline?: string | null;
  expected_result: string | null;
  status: string; // "open" | "in_progress" | "done"
  created_at: string;
  updated_at: string;
};

export type CreateActionItemRequest = {
  showcase_event_id: number;
  task: string;
  assigned_user_id?: number | null;
  department_id: number;
  deadline?: string;
  expected_result: string;
};
export type GetActionItemsParams = {
  // подстрока без учёта регистра
  task?: string;
  // точное совпадение
  status?: string;
  assigned_user_id?: number;
  showcase_event_id?: number;
  // для analyst/admin — фильтр по отделу; для viewer игнорируется
  department_id?: number;
};
type UpdateActionItemRequest = {
  status?: string;
  expected_result?: string;
  // только для analyst/admin:
  task?: string;
  department_id?: number;
  deadline?: string;
  assigned_user_id?: number | null;
};
export const actionApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    createActionItem: builder.mutation<ActionItem, CreateActionItemRequest>({
      query: (body) => ({
        url: "/action-items",
        method: "POST",
        body,
      }),
      invalidatesTags: ["ActionItem"],
    }),
    getActionItems: builder.query<ActionItem[], GetActionItemsParams | void>({
      query: (params) => {
        const sp = new URLSearchParams();
        if (params?.task) sp.set("task", params.task);
        if (params?.status) sp.set("status", params.status);
        if (params?.assigned_user_id != null)
          sp.set("assigned_user_id", String(params.assigned_user_id));
        if (params?.showcase_event_id != null)
          sp.set("showcase_event_id", String(params.showcase_event_id));
        if (params?.department_id != null)
          sp.set("department_id", String(params.department_id));
        const qs = sp.toString();
        return qs ? `/action-items?${qs}` : "/action-items";
      },
      providesTags: ["ActionItem"],
    }),
    getActionItemById: builder.query<ActionItem, number>({
      query: (id) => `/action-items/${id}`,
      providesTags: (_result, _error, id) => [{ type: "ActionItem", id }],
    }),
    updateActionItem: builder.mutation<
      ActionItem,
      { id: number; body: UpdateActionItemRequest }
    >({
      query: ({ id, body }) => ({
        url: `/action-items/${id}`,
        method: "PATCH",
        body,
      }),
      invalidatesTags: (_result, _error, { id }) => [{ type: "ActionItem", id }, "ActionItem"],
    }),
  }),
});

export const {
  useGetActionItemsQuery,
  useGetActionItemByIdQuery,
  useCreateActionItemMutation,
  useUpdateActionItemMutation,
} = actionApi;
