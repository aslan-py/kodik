import { createSlice, type PayloadAction } from "@reduxjs/toolkit";
import type { RootState } from "@/store/types";

export type Permission = "pending" | "viewer" | "analyst" | "admin";

export type AuthUser = {
  id: string;
  name: string;
  email: string;
  role: string;
  permissions: Permission[];
};

export type AuthState = {
  user: AuthUser | null;
  isAuthenticated: boolean;
  status: "idle" | "loading" | "succeeded" | "failed";
};

const initialState: AuthState = {
  user: null,
  isAuthenticated: false,
  status: "idle",
};

const authSlice = createSlice({
  name: "auth",
  initialState,
  reducers: {
    setUser(state, action: PayloadAction<AuthUser>) {
      state.user = action.payload;
      state.isAuthenticated = true;
      state.status = "succeeded";
    },
    clearUser(state) {
      state.user = null;
      state.isAuthenticated = false;
      state.status = "idle";
    },
    setStatus(state, action: PayloadAction<AuthState["status"]>) {
      state.status = action.payload;
    },
  },
});

export const { setUser, clearUser, setStatus } = authSlice.actions;
export const selectUser = (state: RootState) => state.auth.user;
export const selectIsAuthenticated = (state: RootState) =>
  state.auth.isAuthenticated;
export const selectAuthStatus = (state: RootState) => state.auth.status;

export const selectHasPermission =
  (permission: Permission) =>
  (state: RootState): boolean =>
    state.auth.user?.permissions.includes(permission) ?? false;

export const authReducer = authSlice.reducer;
