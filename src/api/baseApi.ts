// src/api/baseApi.ts
import { createApi, fetchBaseQuery } from "@reduxjs/toolkit/query/react";
import { clearUser } from "@/store/authSlice";

const baseQuery = fetchBaseQuery({
  baseUrl: "/api",
  credentials: "include",
});

const baseQueryWithReauth: typeof baseQuery = async (args, api, extraOptions) => {
  const result = await baseQuery(args, api, extraOptions);

  // 401 — токен истёк, сервер сам попробует обновить через refresh cookie
  if (result.error?.status === 401) {
    // Пробуем обновить токен
    const refreshResult = await baseQuery(
      { url: "/auth/refresh", method: "POST" },
      api,
      extraOptions,
    );

    if (refreshResult.error) {
      // Refresh тоже не сработал — разлогиниваем
      api.dispatch(clearUser());
      window.location.href = "/login";
      return result;
    }

    // Повторяем исходный запрос
    return await baseQuery(args, api, extraOptions);
  }

  return result;
};

export const baseApi = createApi({
  reducerPath: "baseApi",
  baseQuery: baseQueryWithReauth,
  tagTypes: ["Incidents", "Tasks", "Sources", "Comments"],
  endpoints: () => ({}), // injectEndpoints в дочерних API
});