// src/store/types.ts
import { baseApi } from "@/api/baseApi";
import { fakeApi } from "@/api/fakeApi";
import type { AuthState } from "./authSlice";

export type RootState = {
  [baseApi.reducerPath]: ReturnType<typeof baseApi.reducer>;
  [fakeApi.reducerPath]: ReturnType<typeof fakeApi.reducer>;
  auth: AuthState;
};