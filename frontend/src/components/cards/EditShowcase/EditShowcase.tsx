"use client";

import { useEffect, useMemo, useState } from "react";
import { Select } from "@/components/ui/Select";
import { Input } from "@/components/ui/Input";
import { DateTimePicker } from "@/components/ui/DatePicker/DatePicker";
import { Button } from "@/components/ui/Button";
import {
  useGetDepartmentsQuery,
  useGetCategoriesQuery,
} from "@/api/adminSourceApi";
import {
  useUpdateShowcaseMutation,
  type Showcase,
  type PriorityLevel,
  type Tonality,
} from "@/api/showcaseApi";
import {
  priorityOptions,
  tonalityOptions,
  matchOptionValue,
} from "@/constants/showcaseEnums";
import { formatDate } from "@/helpers/date";

export type EditShowcaseProps = {
  showcase: Showcase;
  onSuccess: () => void;
  onError?: () => void;
  onCancel: () => void;
};

type FormErrors = {
  department?: string;
  category?: string;
};

export function EditShowcase({
  showcase,
  onSuccess,
  onError,
  onCancel,
}: EditShowcaseProps) {
  const [updateShowcase, { isLoading }] = useUpdateShowcaseMutation();

  const { data: departments = [] } = useGetDepartmentsQuery({
    is_active: true,
  });
  const { data: categories = [] } = useGetCategoriesQuery({
    is_active: true,
  });

  const departmentOptions = useMemo(
    () => departments.map((d) => ({ label: d.name, value: String(d.id) })),
    [departments],
  );
  const categoryOptions = useMemo(
    () => categories.map((c) => ({ label: c.name, value: String(c.id) })),
    [categories],
  );

  const [priority, setPriority] = useState<PriorityLevel | "">(
    matchOptionValue(priorityOptions, showcase.priority),
  );
  const [tonality, setTonality] = useState<Tonality | "">(
    matchOptionValue(tonalityOptions, showcase.tonality),
  );
  const [department, setDepartment] = useState("");
  const [category, setCategory] = useState("");
  const [action, setAction] = useState(showcase.action ?? "");
  const [date, setDate] = useState<Date | undefined>(
    showcase.deadline ? new Date(showcase.deadline) : undefined,
  );
  const [comment, setComment] = useState(showcase.comment ?? "");
  const [errors, setErrors] = useState<FormErrors>({});

  useEffect(() => {
    setPriority(matchOptionValue(priorityOptions, showcase.priority));
    setTonality(matchOptionValue(tonalityOptions, showcase.tonality));
    setAction(showcase.action ?? "");
    setDate(showcase.deadline ? new Date(showcase.deadline) : undefined);
    setComment(showcase.comment ?? "");
  }, [showcase]);

  useEffect(() => {
    if (!departments.length) return;
    const match = departments.find((d) => d.name === showcase.department);
    setDepartment(match ? String(match.id) : "");
  }, [departments, showcase.department]);

  useEffect(() => {
    if (!categories.length) return;
    const match = categories.find((c) => c.name === showcase.category);
    setCategory(match ? String(match.id) : "");
  }, [categories, showcase.category]);

  const clearError = (field: keyof FormErrors) => {
    setErrors((prev) => ({ ...prev, [field]: undefined }));
  };

  const validate = (): FormErrors => {
    const newErrors: FormErrors = {};
    if (!department) newErrors.department = "Выберите ответственный отдел";
    if (!category) newErrors.category = "Выберите категорию";
    return newErrors;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isLoading) return;

    const validationErrors = validate();
    setErrors(validationErrors);
    if (Object.keys(validationErrors).length > 0) return;

    try {
      const result = await updateShowcase({
        id: showcase.id,
        body: {
          priority: priority || null,
          tonality: tonality || null,
          category_id: category ? Number(category) : null,
          action: action.trim() ? action : null,
          deadline: date ? formatDate(date) : null,
          department_id: department ? Number(department) : null,
          comment: comment.trim() ? comment : null,
        },
      }).unwrap();

      if (result) onSuccess();
      else onError?.();
    } catch {
      onError?.();
    }
  };

  return (
    <form className="space-y-4 text-sm" onSubmit={handleSubmit}>
      <p className="font-medium">Редактирование события</p>

      <div>
        <p className="text-(--color-secondary) mb-2">Приоритет</p>
        <Select
          className="surface-block interactive-surface"
          value={priority}
          placeholder="Выберите приоритет"
          options={priorityOptions}
          onChange={(v) => setPriority(v as PriorityLevel)}
        />
      </div>

      <div>
        <p className="text-(--color-secondary) mb-2">Тональность</p>
        <Select
          className="surface-block interactive-surface"
          value={tonality}
          placeholder="Выберите тональность"
          options={tonalityOptions}
          onChange={(v) => setTonality(v as Tonality)}
        />
      </div>

      <div>
        <p className="text-(--color-secondary) mb-2">Категория</p>
        <Select
          className="surface-block interactive-surface"
          value={category}
          placeholder="Выберите категорию"
          options={categoryOptions}
          onChange={(v) => {
            setCategory(v);
            clearError("category");
          }}
          searchable
          searchPlaceholder="Поиск по категории..."
        />
        {errors.category && (
          <p className="text-red-500 text-xs mt-1">{errors.category}</p>
        )}
      </div>

      <div>
        <p className="text-(--color-secondary) mb-2">Ответственный отдел</p>
        <Select
          className="surface-block interactive-surface"
          value={department}
          placeholder="Выберите отдел"
          options={departmentOptions}
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
        <p className="text-(--color-secondary) mb-2">Рекомендуемое действие</p>
        <Input
          id="showcase-action"
          multiline
          height="74px"
          inputClassName="py-3"
          placeholder="Укажите рекомендуемое действие"
          value={action}
          onChange={setAction}
        />
      </div>

      <div>
        <p className="text-(--color-secondary) mb-2">Срок реакции</p>
        <DateTimePicker value={date} withTime={false} onChange={setDate} />
      </div>

      <div>
        <p className="text-(--color-secondary) mb-2">Комментарий</p>
        <Input
          id="showcase-comment"
          multiline
          height="74px"
          inputClassName="py-3"
          placeholder="Добавьте комментарий"
          value={comment}
          onChange={setComment}
        />
      </div>

      <div className="flex justify-end gap-2">
        <Button type="button" onClick={onCancel}>
          Отмена
        </Button>
        <Button type="submit" disabled={isLoading}>
          {isLoading ? "Сохранение..." : "Сохранить"}
        </Button>
      </div>
    </form>
  );
}