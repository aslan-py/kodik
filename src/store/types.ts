// src/store/types.ts
import { authApi } from "@/api/authApi";
import { baseApi } from "@/api/baseApi";
import { fakeApi } from "@/api/fakeApi";
import type { AuthState } from "./authSlice";

export type RootState = {
  [authApi.reducerPath]: ReturnType<typeof authApi.reducer>;
  [baseApi.reducerPath]: ReturnType<typeof baseApi.reducer>;
  [fakeApi.reducerPath]: ReturnType<typeof fakeApi.reducer>;
  auth: AuthState;
};