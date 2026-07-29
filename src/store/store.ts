import { configureStore } from "@reduxjs/toolkit";
import incidentsReducer from "./incidentsSlice";

export const store = configureStore({
    reducer: {
        incidents: incidentsReducer,
    },
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;