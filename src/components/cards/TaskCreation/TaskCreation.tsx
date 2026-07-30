"use client";

import { useState } from "react";
import Button from "@/components/ui/Button/button";
import { DateInput } from "@/components/inputs/DateInput";
import { TextInput } from "@/components/inputs/TextInput";
import { Select, SelectItem } from "@/components/ui/Select";

export function TaskCreation() {
  const [showComment, setShowComment] = useState(false);
  const [comment, setComment] = useState("");

  return (
    <div className="space-y-4 text-sm">
      <p className="font-medium">Создание задачи</p>
      <div>
        <p className="text-[var(--color-secondary)] mb-2">Требуемое действие</p>
        <TextInput
          multiline
          width=""
          height="120px"
          inputClassName="py-3"
          value="Короткая оценка риска, список ответных действий и рекомендация по коммуникации для селлеров."
          onChange={() => {}}
        />
      </div>
      <div>
        <p className="text-[var(--color-secondary)] mb-2">Ответственный отдел</p>
        <Select
          className="surface-block interactive-surface"
          buttonContent={"Выберите отдел"}
        >
          <SelectItem onClick={() => {}}>Коммерческий отдел</SelectItem>
          <SelectItem onClick={() => {}}>Финансовый отдел</SelectItem>
        </Select>
      </div>
      <div>
        <p className="text-[var(--color-secondary)] mb-2">Срок</p>
        <DateInput value="" onChange={() => {}} />
      </div>
      <div>
        <p className="text-[var(--color-secondary)] mb-2">Ожидаемый результат</p>
        <TextInput
          inputClassName="py-3"
          value="Короткая оценка риска, список ответных действий и рекомендация по коммуникации для селлеров."
          onChange={() => {}}
        />
      </div>
      {showComment ? (
        <div>
          <p className="text-[var(--color-secondary)] mb-2">Комментарий</p>
          <TextInput
            multiline
            inputClassName="py-3"
            value={comment}
            onChange={setComment}
          />
        </div>
      ) : (
        <button
          onClick={() => setShowComment(true)}
          className="text-[var(--color-accent)] text-sm cursor-pointer bg-transparent border-none p-0 text-left"
        >
          + Комментарий
        </button>
      )}
    </div>
  );
}