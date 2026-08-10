// @/hooks/useDepartmentName.ts
import { useGetDepartmentsQuery } from "@/api/adminSourceApi";
import { useMemo } from "react";


export function useDepartmentsMap() {
  const { data: departments = [] } = useGetDepartmentsQuery();

  return useMemo(() => {
    return new Map(departments.map((d) => [d.id, d.name]));
  }, [departments]);
}

export function useDepartmentName(departmentId: number | null | undefined): string {
  const departmentsMap = useDepartmentsMap();
  if (departmentId == null) return "—";
  return departmentsMap.get(departmentId) ?? "—";
}