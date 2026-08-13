"use client";

import { useDepartmentName } from "@/hooks/useDepartament";

import { statusLabel } from "@/helpers/status";

export type RelatedTaskData = {
  id: number;
  task: string;
  status: string;
  deadline?: string | null;
  expected_result?: string | null;
  department_id?: number | null;
  assigned_user_id?: number | null;
};

type RelatedTaskProps = {
  relatedTask: RelatedTaskData;
  label?: string;
  onClick?: () => void;
};

export function RelatedTask({ relatedTask, label, onClick }: RelatedTaskProps) {
  const departmentName = useDepartmentName(relatedTask.department_id);
  // const assignedUserName = useUserName(relatedTask.assigned_user_id);
  const assignedUserName = relatedTask.assigned_user_id;

  const parts: string[] = [];
  if (relatedTask.department_id != null) {
    parts.push(`Отдел ${departmentName}`);
  }
  parts.push(statusLabel(relatedTask.status));
  if (relatedTask.assigned_user_id != null) {
    parts.push(`Исполнитель ${assignedUserName}`);
  }
  if (relatedTask.deadline) {
    parts.push(`до ${relatedTask.deadline.slice(0, 10)}`);
  }
  const details = parts.join(" · ");

  return (
    <div className="space-y-4 text-sm">
      <p className="font-medium">{label ?? "Связанная задача"}</p>
      <button
        className="surface-block interactive-surface flex flex-col items-start p-4 w-full text-left rounded-lg cursor-pointer"
        onClick={onClick}
      >
        <span className="text-sm font-medium">{relatedTask.task}</span>
        <span className="text-xs text-(--color-secondary) font-normal mb-2 mt-auto pt-2">
          {details}
        </span>
        {relatedTask.expected_result && (
          <p className="text-(--color-secondary) text-xs">
            {relatedTask.expected_result}
          </p>
        )}
      </button>
    </div>
  );
}
