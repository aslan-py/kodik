// src/api/baseApi.ts
import { createApi, fetchBaseQuery } from "@reduxjs/toolkit/query/react";
import { getAccessToken, clearAccessToken } from "@/helpers/cookies";

const baseQuery = fetchBaseQuery({
  baseUrl: "http://127.0.0.1:8000",
  // baseUrl: process.env.NEXT_PUBLIC_API_URL,
  prepareHeaders: (headers) => {
    const token = getAccessToken();
    if (token) {
      headers.set("Authorization", `Bearer ${token}`);
    }
    return headers;
  },
});

const AUTH_ENDPOINTS_EXEMPT_FROM_GLOBAL_401 = ["/auth/login", "/auth/register"];

const baseQueryWithAuth: typeof baseQuery = async (args, api, extraOptions) => {
  const result = await baseQuery(args, api, extraOptions);

  const url = typeof args === "string" ? args : args.url;
  const isExempt = AUTH_ENDPOINTS_EXEMPT_FROM_GLOBAL_401.some((path) =>
    url.startsWith(path),
  );

  if (result.error?.status === 401 && !isExempt) {
    clearAccessToken();
    // диспатчим тип экшена напрямую, БЕЗ импорта action-creator'а из authSlice —
    // это и есть разрыв цикла baseApi → authSlice → usersApi → baseApi
    api.dispatch({ type: "auth/logout" });
    window.location.href = "/login";
  }

  return result;
};

export const baseApi = createApi({
  reducerPath: "baseApi",
  baseQuery: baseQueryWithAuth,
  tagTypes: ["Showcases"],
  endpoints: () => ({}),
});