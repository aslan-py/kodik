"use client";

import { useMemo, useState } from "react";

import { Select } from "@/components/ui/Select";
import { Input } from "@/components/ui/Input";
import { DateTimePicker } from "@/components/ui/DatePicker/DatePicker";
import type { ActionItem, CreateActionItemRequest } from "@/api/actionApi";

type TaskCreationProps = {
  incidentId?: number;
  onSubmit?: (data: CreateActionItemRequest) => Promise<ActionItem>;
  onSuccess?: (created: ActionItem) => void;
  onError?: () => void;
  onLoadingChange?: (loading: boolean) => void;
};

type FormErrors = {
  action?: string;
  department?: string;
  deadline?: string;
  expectedResult?: string;
};

// TODO: заменить на реальный список отделов из API, когда появится departmentsApi
const DEPARTMENT_OPTIONS = [
  { label: "Коммерческий отдел", value: "1" },
  { label: "Финансовый отдел", value: "2" },
  { label: "Логистический отдел", value: "3" },
  { label: "Юридический отдел", value: "4" },
];

// TODO: заменить на реальный поиск через usersApi, когда появится эндпоинт
type UserOption = { id: number; name: string };
const MOCK_USERS: UserOption[] = [
  { id: 1, name: "Иванов Иван" },
  { id: 2, name: "Петрова Анна" },
  { id: 3, name: "Сидоров Пётр" },
  { id: 4, name: "Кузнецова Мария" },
];

export function TaskCreation({
  incidentId,
  onSubmit,
  onSuccess,
  onError,
  onLoadingChange,
}: TaskCreationProps) {
  const [showComment, setShowComment] = useState(false);
  const [comment, setComment] = useState("");
  const [action, setAction] = useState("");
  const [department, setDepartment] = useState("");
  const [date, setDate] = useState<Date>();
  const [expectedResult, setExpectedResult] = useState("");
  const [errors, setErrors] = useState<FormErrors>({});

  const [userQuery, setUserQuery] = useState("");
  const [assignedUser, setAssignedUser] = useState<UserOption | null>(null);

  const userResults = useMemo(() => {
    const q = userQuery.trim().toLowerCase();
    if (!q) return [];
    return MOCK_USERS.filter((u) => u.name.toLowerCase().includes(q));
  }, [userQuery]);

  const validate = (): FormErrors => {
    const newErrors: FormErrors = {};
    if (!action.trim()) newErrors.action = "Укажите требуемое действие";
    if (!department) newErrors.department = "Выберите ответственный отдел";

    if (!date) {
      newErrors.deadline = "Укажите срок";
    } else if (date.getTime() < Date.now()) {
      newErrors.deadline = "Срок не может быть в прошлом";
    } else {
      const maxDate = new Date(new Date().getFullYear() + 1, 11, 31, 23, 59, 59);
      if (date.getTime() > maxDate.getTime()) {
        newErrors.deadline = "Дата не может быть позже конца следующего года";
      }
    }

    if (!expectedResult.trim())
      newErrors.expectedResult = "Укажите ожидаемый результат";
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
    if (!incidentId || !date) return;

    const data: CreateActionItemRequest = {
      showcase_id: incidentId,
      title: action,
      department_id: Number(department),
      deadline: date.toISOString(),
      expected_result: expectedResult,
      assigned_user_id: assignedUser?.id ?? null,
    };

    onLoadingChange?.(true);
    try {
      const created = await onSubmit?.(data);
      if (created) onSuccess?.(created);
    } catch {
      onError?.();
    } finally {
      onLoadingChange?.(false);
    }
  };

  return (
    <form id="task-creation-form" className="space-y-4 text-sm" onSubmit={handleSubmit}>
      <p className="font-medium">Создание задачи</p>
      <div>
        <p className="text-(--color-secondary) mb-2">Требуемое действие</p>
        <Input
          id="task-action"
          multiline
          height="74px"
          inputClassName="py-3"
          value={action}
          onChange={(v) => {
            setAction(v);
            clearError("action");
          }}
        />
        {errors.action && <p className="text-red-500 text-xs mt-1">{errors.action}</p>}
      </div>
      <div>
        <p className="text-(--color-secondary) mb-2">Ответственный отдел</p>
        <Select
          className="surface-block interactive-surface"
          value={department}
          placeholder="Выберите отдел"
          options={DEPARTMENT_OPTIONS}
          onChange={(v) => {
            setDepartment(v);
            clearError("department");
          }}
        />
        {errors.department && <p className="text-red-500 text-xs mt-1">{errors.department}</p>}
      </div>
      <div>
        <p className="text-(--color-secondary) mb-2">Исполнитель</p>
        {assignedUser ? (
          <div className="flex items-center justify-between rounded-lg border border-(--color-border) px-3 py-2">
            <span className="text-xs text-(--color-ink)">{assignedUser.name}</span>
            <button
              type="button"
              onClick={() => setAssignedUser(null)}
              className="text-(--color-accent) text-xs cursor-pointer bg-transparent border-none p-0"
            >
              Изменить
            </button>
          </div>
        ) : (
          <div className="relative">
            <Input
              id="task-assignee-search"
              value={userQuery}
              onChange={setUserQuery}
              placeholder="Поиск по имени..."
            />
            {userResults.length > 0 && (
              <div className="absolute z-10 mt-1 w-full rounded-lg border border-(--color-border) bg-(--color-surface) shadow-md">
                {userResults.map((u) => (
                  <button
                    key={u.id}
                    type="button"
                    onClick={() => {
                      setAssignedUser(u);
                      setUserQuery("");
                    }}
                    className="block w-full text-left px-3 py-2 text-xs hover:bg-(--color-surface-hover) bg-transparent border-none cursor-pointer"
                  >
                    {u.name}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
      <div>
        <p className="text-(--color-secondary) mb-2">Срок</p>
        <DateTimePicker
          value={date}
          onChange={(v) => {
            setDate(v);
            clearError("deadline");
          }}
        />
        {errors.deadline && <p className="text-red-500 text-xs mt-1">{errors.deadline}</p>}
      </div>
      <div>
        <p className="text-(--color-secondary) mb-2">Ожидаемый результат</p>
        <Input
          id="task-expected-result"
          multiline
          height="74px"
          inputClassName="py-3"
          value={expectedResult}
          onChange={(v) => {
            setExpectedResult(v);
            clearError("expectedResult");
          }}
        />
        {errors.expectedResult && (
          <p className="text-red-500 text-xs mt-1">{errors.expectedResult}</p>
        )}
      </div>
      {showComment ? (
        <div>
          <p className="text-(--color-secondary) mb-2">Комментарий</p>
          <Input
            id="task-comment"
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