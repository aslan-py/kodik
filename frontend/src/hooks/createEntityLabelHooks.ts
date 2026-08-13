// @/hooks/createEntityLabelHooks.ts
import { useMemo } from "react";
import { useLabelFor, useLabelMap, LabelOption } from "./useLabelMap";

type HasIdAndName = { id: number; name: string };

export function createEntityLabelHooks<T extends HasIdAndName>(
  useQuery: (arg?: any) => { data?: T[] | undefined },
  getLabel: (item: T) => string = (item: any) => item.name,
) {
  function useOptions(): LabelOption<number>[] {
    const { data = [] } = useQuery();
    return useMemo(
      () => data.map((d) => ({ label: getLabel(d), value: d.id })),
      [data],
    );
  }

  function useMap() {
    return useLabelMap(useOptions());
  }

  function useName(id: number | null | undefined): string {
    return useLabelFor(useOptions(), id);
  }

  return { useOptions, useMap, useName };
}


// export const { useOptions: useSourceOptions, ... } = createEntityLabelHooks(
//   useGetAllSourcesQuery,
//   (s) => s.title, // если поле называется иначе
// );