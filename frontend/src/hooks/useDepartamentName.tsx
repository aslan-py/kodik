// @/hooks/useDepartments.ts
// ! убрать из проектта отсавить useDepartamen
import { useGetDepartmentsQuery } from "@/api/adminSourceApi";
import { useMemo } from "react";
import { useLabelFor, useLabelMap } from "./useLabelMap";

export function useDepartmentOptions() {
  const { data: departments = [] } = useGetDepartmentsQuery();
  return useMemo(
    () => departments.map((d) => ({ label: d.name, value: d.id })),
    [departments],
  );
}

export function useDepartmentsMap() {
  return useLabelMap(useDepartmentOptions());
}

export function useDepartmentName(departmentId: number | null | undefined) {
  return useLabelFor(useDepartmentOptions(), departmentId);
}