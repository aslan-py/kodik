"use client";

import { useState } from "react";

import { Select } from "@/components/ui/Select";
import type { TaskCreatePayload } from "@/types/task";
import { Input } from "@/components/ui/Input";
import { DateTimePicker } from "@/components/ui/DatePicker/DatePicker";

type TaskCreationProps = {
  incidentId?: string;
  onSubmit?: (data: TaskCreatePayload) => void | Promise<unknown>;
  onSuccess?: () => void;
  onError?: () => void;
  onLoadingChange?: (loading: boolean) => void;
};

type FormErrors = {
  action?: string;
  department?: string;
  deadline?: string;
  expectedResult?: string;
};

export function TaskCreation({ incidentId, onSubmit, onSuccess, onError, onLoadingChange }: TaskCreationProps) {
  const [showComment, setShowComment] = useState(false);
  const [comment, setComment] = useState("");
  const [action, setAction] = useState("");
  const [department, setDepartment] = useState("");
  const [deadline, setDeadline] = useState("");
  const [expectedResult, setExpectedResult] = useState("");
  const [errors, setErrors] = useState<FormErrors>({});
  const [date, setDate] = useState<Date>();

  const validate = (): FormErrors => {
    const newErrors: FormErrors = {};
    if (!action.trim()) newErrors.action = "Укажите требуемое действие";
    if (!department) newErrors.department = "Выберите ответственный отдел";
    if (!deadline.trim()) {
      newErrors.deadline = "Укажите срок";
    } else if (!/^\d{2}-\d{2}-\d{4} \d{2}:\d{2}$/.test(deadline.trim())) {
      newErrors.deadline = "Формат: MM-DD-YYYY HH:mm";
    } else {
      const [month, day, yearAndTime] = deadline.split("-");
      const [year, timePart] = yearAndTime.split(" ");
      const isoDate = `${year}-${month}-${day}T${timePart}`;
      const parsed = new Date(isoDate);
      if (isNaN(parsed.getTime())) {
        newErrors.deadline = "Некорректная дата";
      } else if (parsed.getTime() < Date.now()) {
        newErrors.deadline = "Срок не может быть в прошлом";
      } else {
        const maxDate = new Date(new Date().getFullYear() + 1, 11, 31, 23, 59, 59);
        if (parsed.getTime() > maxDate.getTime()) {
          newErrors.deadline = "Дата не может быть позже конца следующего года";
        }
      }
    }
    if (!expectedResult.trim()) newErrors.expectedResult = "Укажите ожидаемый результат";
    return newErrors;
  };

  const clearError = (field: keyof FormErrors) => {
    setErrors((prev) => ({ ...prev, [field]: undefined }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const validationErrors = validate();
    setErrors(validationErrors);
    if (Object.keys(validationErrors).length > 0) return;

    const data = {
      incidentId: incidentId ?? "",
      action,
      department,
      deadline,
      expectedResult,
      comment: comment || undefined,
    };

    console.log("[TaskCreation] отправка задачи:", data);

    onLoadingChange?.(true);
    try {
      await onSubmit?.(data);
      onSuccess?.();
    } catch {
      onError?.();
    } finally {
      onLoadingChange?.(false);
    }
  };

  return (
    <form
      id="task-creation-form"
      className="space-y-4 text-sm"
      onSubmit={handleSubmit}
    >
      <p className="font-medium">Создание задачи</p>
      <div>
        <p className="text-(--color-secondary) mb-2">Требуемое действие</p>
        <Input id=""
          multiline
          height="74px"
          inputClassName="py-3"
          value={action}
          onChange={(v) => { setAction(v); clearError("action"); }}
        />
        {errors.action && <p className="text-red-500 text-xs mt-1">{errors.action}</p>}
      </div>
      <div>
        <p className="text-(--color-secondary) mb-2">Ответственный отдел</p>
        <Select
          className="surface-block interactive-surface"
          value={department}
          placeholder="Выберите отдел"
          options={[
            { label: "Коммерческий отдел", value: "Коммерческий отдел" },
            { label: "Финансовый отдел", value: "Финансовый отдел" },
          ]}
          onChange={(v) => { setDepartment(v); clearError("department"); }}
        />
        {errors.department && <p className="text-red-500 text-xs mt-1">{errors.department}</p>}
      </div>
      <div>
        <p className="text-(--color-secondary) mb-2">Срок</p>
       <DateTimePicker value={date} onChange={setDate} />

        {errors.deadline && <p className="text-red-500 text-xs mt-1">{errors.deadline}</p>}
      </div>
      <div>
        <p className="text-(--color-secondary) mb-2">Ожидаемый результат</p>
        <Input id=""
          multiline
          height="74px"
          inputClassName="py-3"
          value={expectedResult}
          onChange={(v) => { setExpectedResult(v); clearError("expectedResult"); }}
        />
        {errors.expectedResult && <p className="text-red-500 text-xs mt-1">{errors.expectedResult}</p>}
      </div>
      {showComment ? (
        <div>
          <p className="text-(--color-secondary) mb-2">Комментарий</p>
          <Input id=""
            multiline
            height="74px"
            inputClassName="py-3"
            value={comment}
            onChange={setComment}
          />
        </div>
      ) : (
        <button
          type="button"
          onClick={() => setShowComment(true)}
          className="text-(--color-accent) text-sm cursor-pointer bg-transparent border-none p-0 text-left"
        >
          + Комментарий
        </button>
      )}
     
    </form>
  );
}