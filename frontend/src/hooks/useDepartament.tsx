// @/hooks/useDepartments.ts
import { useGetDepartmentsQuery } from "@/api/adminSourceApi";
import { createEntityLabelHooks } from "./createEntityLabelHooks";

export const {
  // для выпадающих списков
  // Возвращает массив { label, value }, готовый под Select/фильтры:
  // tsx
  // const options = useDepartmentOptions();
  // // [{
  useOptions: useDepartmentOptions,
  //   2. useDepartmentsMap() — когда нужен быстрый лукап по id

  // Возвращает Map<number, string>. Полезно, если в одном месте нужно резолвить много id за раз (например, таблица с колонкой "Отдел", где на каждую строку смотришь map.get(row.department_id)), — так эффективнее, чем гонять useDepartmentName в цикле (каждый вызов useName внутри себя строит свой Map через useLabelMap, так что при большом списке лучше построить Map один раз и переиспользовать).
  useMap: useDepartmentsMap,
  //   Самый простой случай — когда нужно показать название отдела для одного конкретного id, без ручного построения Map:

  // tsx
  // const departmentName = useDepartmentName(user?.department_id);
  // // "Отдел разработки" или "—" (fallback), если id не найден/null
  useName: useDepartmentName,
} = createEntityLabelHooks(useGetDepartmentsQuery);
