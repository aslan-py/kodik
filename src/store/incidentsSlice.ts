import {
  createSlice,
  createAsyncThunk,
  createSelector,
} from "@reduxjs/toolkit";
import type { IncidentItem } from "@/types/types";
import { fetchIncidents as fetchIncidentsApi } from "@/api/incidents";
import type { RootState } from "./store";

interface IncidentsState {
  items: IncidentItem[];
  loading: boolean;
  error: string | null;
}

const initialState: IncidentsState = {
  items: [],
  loading: true,
  error: null,
};

export const loadIncidents = createAsyncThunk("incidents/load", async () => {
  const data = await fetchIncidentsApi();
  return data;
});

const incidentsSlice = createSlice({
  name: "incidents",
  initialState,
  reducers: {},
  extraReducers: (builder) => {
    builder
      .addCase(loadIncidents.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(loadIncidents.fulfilled, (state, action) => {
        state.items = action.payload;
        state.loading = false;
      })
      .addCase(loadIncidents.rejected, (state, action) => {
        state.loading = false;
        state.error = action.error.message ?? "Ошибка загрузки";
      });
  },
  selectors: {
    selectAllIncidents: (state) => state.items,
    selectIncidentsLoading: (state) => state.loading,
    selectIncidentsError: (state) => state.error,
  },
});
export const {
  selectAllIncidents,
  selectIncidentsLoading,
  selectIncidentsError,
} = incidentsSlice.selectors;

export default incidentsSlice.reducer;
