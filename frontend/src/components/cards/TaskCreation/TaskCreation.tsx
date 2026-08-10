"use client";

import { useEffect, useMemo, useState, useRef } from "react";

import { Select } from "@/components/ui/Select";
import { Input } from "@/components/ui/Input";
import { DateTimePicker } from "@/components/ui/DatePicker/DatePicker";
import { useGetDepartmentsQuery } from "@/api/adminSourceApi";
import {
  useCreateActionItemMutation,
  useUpdateActionItemMutation,
  type ActionItem,
  type CreateActionItemRequest,
} from "@/api/actionApi";
import { Button } from "@/components/ui/Button";
import { formatDate } from "@/helpers/date";
import { statusLabel } from "@/helpers/status";
import { AuthUser } from "@/store/authSlice";
import { useGetAllUsersQuery } from "@/api/usersApi";
import { usePermission } from "@/hooks/useAuth";


const STATUS_VALUES = ["open", "in_progress", "done"] as const;
const statusOptions = STATUS_VALUES.map((value) => ({
  label: statusLabel(value),
  value,
}));

type TaskCreationProps = {
  incidentId?: number;
  incidentDeadline?: string;
  isEditing?: boolean;
  initialData?: ActionItem;
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

export function TaskCreation({
  incidentId,
  incidentDeadline,
  isEditing = false,
  initialData,
  onSubmit,
  onSuccess,
  onError,
  onLoadingChange,
}: TaskCreationProps) {
  const isAdmin = usePermission(["analyst", "admin"]);

  const [action, setAction] = useState(initialData?.task ?? "");
  const [department, setDepartment] = useState(
    initialData?.department_id != null ? String(initialData.department_id) : "",
  );
  const [date, setDate] = useState<Date | undefined>(
    initialData?.deadline ? new Date(initialData.deadline) : undefined,
  );
  const [expectedResult, setExpectedResult] = useState(
    initialData?.expected_result ?? "",
  );
  const [status, setStatus] = useState(initialData?.status ?? STATUS_VALUES[0]);
  const [errors, setErrors] = useState<FormErrors>({});

  const [userQuery, setUserQuery] = useState("");
  const [assignedUser, setAssignedUser] = useState<AuthUser | null>(null);
  const [isAssigneeFocused, setIsAssigneeFocused] = useState(false);
  const blurTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const [createActionItem, { isLoading: isCreating }] =
    useCreateActionItemMutation();
  const [updateActionItem, { isLoading: isUpdating }] =
    useUpdateActionItemMutation();
  const isLoading = isCreating || isUpdating;

  const { data: departments = [] } = useGetDepartmentsQuery({
    is_active: true,
  });
  const departmentOptions = useMemo(
    () => departments.map((d) => ({ label: d.name, value: String(d.id) })),
    [departments],
  );

  const [debouncedQuery, setDebouncedQuery] = useState("");
  useEffect(() => {
    const t = setTimeout(() => setDebouncedQuery(userQuery.trim()), 300);
    return () => clearTimeout(t);
  }, [userQuery]);

  const searchDepartmentId = department ? Number(department) : undefined;

  const { data: usersData, isFetching: isUsersFetching } = useGetAllUsersQuery(
    searchDepartmentId != null
      ? debouncedQuery
        ? { full_name: debouncedQuery, department_id: searchDepartmentId }
        : { department_id: searchDepartmentId }
      : undefined,
    { skip: searchDepartmentId == null },
  );
  const userResults = isUsersFetching ? [] : (usersData ?? []);
  const showDropdown = isAssigneeFocused && userResults.length > 0;

  const isFirstDeptRender = useMemo(() => ({ current: true }), []);
  useEffect(() => {
    if (isFirstDeptRender.current) {
      isFirstDeptRender.current = false;
      return;
    }
    setAssignedUser(null);
    setUserQuery("");
    setDebouncedQuery("");
    setIsAssigneeFocused(false);
  }, [department]);

  useEffect(() => {
    if (!initialData) return;
    setAction(initialData.task ?? "");
    setDepartment(
      initialData.department_id != null
        ? String(initialData.department_id)
        : "",
    );
    setDate(initialData.deadline ? new Date(initialData.deadline) : undefined);
    setExpectedResult(initialData.expected_result ?? "");
    setStatus(initialData.status ?? STATUS_VALUES[0]);
  }, [initialData]);

  useEffect(() => {
    return () => {
      if (blurTimeoutRef.current) clearTimeout(blurTimeoutRef.current);
    };
  }, []);

  const handleAssigneeBlur = () => {
    blurTimeoutRef.current = setTimeout(() => {
      setIsAssigneeFocused(false);
    }, 150);
  };

  const handleAssigneeFocus = () => {
    if (blurTimeoutRef.current) clearTimeout(blurTimeoutRef.current);
    setIsAssigneeFocused(true);
  };

  // task/department/deadline редактирует: всегда при создании, при редактировании — только admin
  const canEditAdminFields = !isEditing || isAdmin;

  const validate = (): FormErrors => {
    const newErrors: FormErrors = {};

    if (canEditAdminFields) {
      if (!action.trim()) newErrors.action = "Укажите требуемое действие";
      if (!department) newErrors.department = "Выберите ответственный отдел";

      if (!date) {
        newErrors.deadline = "Укажите срок";
      } else if (date.getTime() < Date.now()) {
        newErrors.deadline = "Срок не может быть в прошлом";
      } else {
        const maxDate = new Date(
          new Date().getFullYear() + 1,
          11,
          31,
          23,
          59,
          59,
        );
        if (date.getTime() > maxDate.getTime()) {
          newErrors.deadline = "Дата не может быть позже конца следующего года";
        }
      }
    }

    if (!expectedResult.trim())
      newErrors.expectedResult = "Укажите ожидаемый результат";
    return newErrors;
  };

  const clearError = (field: keyof FormErrors) => {
    setErrors((prev) => ({ ...prev, [field]: undefined }));
  };

  const parseDate = (value?: string): Date | undefined => {
    if (!value) return undefined;
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? undefined : parsed;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (isLoading) return;

    const validationErrors = validate();
    setErrors(validationErrors);
    if (Object.keys(validationErrors).length > 0) return;
    if (canEditAdminFields && !date) return;
    if (!isEditing && !incidentId) return;

    onLoadingChange?.(true);
    try {
      let result: ActionItem;

      if (isEditing && initialData) {
        // status/expected_result — всем; task/department_id/deadline/assigned_user_id — только admin
        const updateBody = {
          status,
          expected_result: expectedResult,
          ...(isAdmin
            ? {
                task: action,
                department_id: Number(department),
                deadline: date ? formatDate(date) : undefined,
                assigned_user_id: assignedUser?.id ?? null,
              }
            : {}),
        };
        result = await updateActionItem({
          id: initialData.id,
          body: updateBody,
        }).unwrap();
      } else {
        // статус на создании не отправляем — сервер ставит его сам
        const createData: CreateActionItemRequest = {
          showcase_event_id: incidentId as number,
          task: action,
          department_id: Number(department),
          deadline: formatDate(date as Date),
          expected_result: expectedResult,
          assigned_user_id: assignedUser?.id ?? null,
        };
        result = onSubmit
          ? await onSubmit(createData)
          : await createActionItem(createData).unwrap();
      }

      if (result && typeof result.id === "number") {
        onSuccess?.(result);
      } else {
        onError?.();
      }
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
      <p className="font-medium">
        {isEditing ? "Редактирование задачи" : "Создание задачи"}
      </p>

      {/* Статус — доступен всем при редактировании; при создании его не показываем,
          сервер ставит дефолтный статус сам */}
      {isEditing && (
        <div>
          <p className="text-(--color-secondary) mb-2">Статус</p>
          <Select
            className="surface-block interactive-surface"
            value={status}
            options={statusOptions}
            onChange={(v) => setStatus(v)}
          />
        </div>
      )}

      <div>
        <p className="text-(--color-secondary) mb-2">Требуемое действие</p>
        <Input
          id="task-action"
          multiline
          height="74px"
          placeholder="Укажите требуемое действие"
          inputClassName="py-3"
          value={action}
          disabled={isEditing && !isAdmin}
          onChange={(v) => {
            setAction(v);
            clearError("action");
          }}
        />
        {errors.action && (
          <p className="text-red-500 text-xs mt-1">{errors.action}</p>
        )}
      </div>

      <div>
        <p className="text-(--color-secondary) mb-2">Ответственный отдел</p>
        <Select
          className="surface-block interactive-surface"
          value={department}
          placeholder="Выберите отдел"
          options={departmentOptions}
          disabled={isEditing && !isAdmin}
          onChange={(v) => {
            setDepartment(v);
            clearError("department");
          }}
        />
        {errors.department && (
          <p className="text-red-500 text-xs mt-1">{errors.department}</p>
        )}
      </div>

      <div>
        <p className="text-(--color-secondary) mb-2">Исполнитель</p>
        {assignedUser ? (
          <div className="flex items-center justify-between rounded-lg border border-(--color-border) px-3 py-2">
            <span className="text-xs text-(--color-ink)">
              {assignedUser.full_name}
            </span>
            {(!isEditing || isAdmin) && (
              <button
                type="button"
                onClick={() => setAssignedUser(null)}
                className="text-(--color-accent) text-xs cursor-pointer bg-transparent border-none p-0"
              >
                Изменить
              </button>
            )}
          </div>
        ) : (
          <div className="relative">
            <Input
              id="task-assignee-search"
              value={userQuery}
              onChange={setUserQuery}
              inputProps={{
                onFocus: handleAssigneeFocus,
                onBlur: handleAssigneeBlur,
              }}
              placeholder={
                searchDepartmentId == null
                  ? "Сначала выберите отдел"
                  : "Поиск по имени..."
              }
              disabled={(isEditing && !isAdmin) || searchDepartmentId == null}
            />
            {showDropdown && (
              <div className="absolute z-10 mt-1 w-full rounded-lg border border-(--color-border) bg-(--color-surface) shadow-md">
                {userResults.map((u) => (
                  <button
                    key={u.id}
                    type="button"
                    onClick={() => {
                      setAssignedUser(u);
                      setUserQuery("");
                      setDebouncedQuery("");
                      setIsAssigneeFocused(false);
                    }}
                    className="block w-full text-left px-3 py-2 text-xs hover:bg-(--color-surface-hover) bg-transparent border-none cursor-pointer"
                  >
                    {u.full_name}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      <div>
        <p className="text-(--color-secondary) mb-2">Срок</p>
        <div className="flex justify-between gap-5">
          <DateTimePicker
            value={date}
            withTime={false}
            disabled={isEditing && !isAdmin}
            onChange={(v) => {
              setDate(v);
              clearError("deadline");
            }}
          />
          {(!isEditing || isAdmin) && (
            <Button variant="secondary" className="max-w-35" fullWidth onClick={() => setDate(parseDate(incidentDeadline))}>
              Как в анализе
            </Button>
          )}
        </div>
        {errors.deadline && (
          <p className="text-red-500 text-xs mt-1">{errors.deadline}</p>
        )}
      </div>

      <div>
        <p className="text-(--color-secondary) mb-2">Ожидаемый результат</p>
        <Input
          id="task-expected-result"
          multiline
          height="74px"
          inputClassName="py-3"
          value={expectedResult}
          placeholder="Укажите ожидаемый результат"
          onChange={(v) => {
            setExpectedResult(v);
            clearError("expectedResult");
          }}
        />
        {errors.expectedResult && (
          <p className="text-red-500 text-xs mt-1">{errors.expectedResult}</p>
        )}
      </div>

      <Button type="submit" disabled={isLoading} className="w-full">
        {isLoading
          ? isEditing
            ? "Сохранение..."
            : "Создание..."
          : isEditing
            ? "Сохранить"
            : "Создать задачу"}
      </Button>
    </form>
  );
}