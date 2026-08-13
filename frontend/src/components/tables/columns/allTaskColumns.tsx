// @/components/tables/columns/allTaskColumns.tsx
import { useMemo } from "react";
import { TableColumn } from "@/components/ui/Table/Table";
import { ActionItem } from "@/api/actionApi";
import { formatDateWithTime } from "@/helpers/date";
import { statusLabel, statusClass } from "@/helpers/status";
import { DeadlineBadge } from "@/components/features/DeadLineBadge";
import { useDepartmentName } from "@/hooks/useDepartamentName";
// department cell как отдельный компонент
function DepartmentCell({ departmentId }: { departmentId: number }) {
  const name = useDepartmentName(departmentId);
  return <span className="block text-(--color-ink)">{name}</span>;
}

export function useAllTaskColumns(): TableColumn<ActionItem>[] {

  return useMemo<TableColumn<ActionItem>[]>(
    () => [
      {
        key: "title",
        header: "Задача",
        render: (item) => (
          <span className="block text-(--color-ink) font-medium max-w-80 truncate">
            {item.task}
          </span>
        ),
      },
      {
        key: "department",
        header: "Отдел",
         render: (item) => <DepartmentCell departmentId={item.department_id} />,
      },
      
      {
        key: "deadline",
        header: "Срок",
        render: (item) => (
          <DeadlineBadge
            deadline={item.deadline}
            isDone={item.status === "done"}
          />
        ),
      },
      {
        key: "status",
        header: "Статус",
        render: (item) => (
          <span className={statusClass(item.status)}>
            {statusLabel(item.status)}
          </span>
        ),
      },
      {
        key: "created_at",
        header: "Создана",
        render: (item) => (
          <span className="block whitespace-nowrap text-(--color-ink)">
            {formatDateWithTime(item.created_at)}
          </span>
        ),
      },
    ],
    [],
  );
}

// // @/components/tables/columns/allTaskColumns.tsx
// import { useMemo } from "react";
// import { TableColumn } from "@/components/ui/Table/Table";
// import { ActionItem } from "@/api/actionApi";
// import { formatDateWithTime } from "@/helpers/date";
// import { statusLabel, statusClass } from "@/helpers/status";
// import { DeadlineBadge } from "@/components/features/DeadLineBadge";
// import { useDepartmentsMap } from "@/hooks/useDepartament";
// import { labelFromMap } from "@/hooks/useLabelMap";

// export function useAllTaskColumns(): TableColumn<ActionItem>[] {
//   const departmentsMap = useDepartmentsMap();

//   return useMemo<TableColumn<ActionItem>[]>(
//     () => [
//       {
//         key: "title",
//         header: "Задача",
//         render: (item) => (
//           <span className="block text-(--color-ink) font-medium max-w-80 truncate">
//             {item.task}
//           </span>
//         ),
//       },
//       {
//         key: "department",
//         header: "Отдел",
//         render: (task) => (
//           <span className="block text-(--color-ink)">
//             {labelFromMap(departmentsMap, task.department_id)}
//           </span>
//         ),
//       },

//       {
//         key: "deadline",
//         header: "Срок",
//         render: (item) => (
//           <DeadlineBadge
//             deadline={item.deadline}
//             isDone={item.status === "done"}
//           />
//         ),
//       },
//       {
//         key: "status",
//         header: "Статус",
//         render: (item) => (
//           <span className={statusClass(item.status)}>
//             {statusLabel(item.status)}
//           </span>
//         ),
//       },
//       {
//         key: "created_at",
//         header: "Создана",
//         render: (item) => (
//           <span className="block whitespace-nowrap text-(--color-ink)">
//             {formatDateWithTime(item.created_at)}
//           </span>
//         ),
//       },
//     ],
//     [],
//   );
// }
