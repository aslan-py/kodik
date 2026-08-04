"use client";

import { useMemo, useState, useCallback } from "react";
import { Card, CardHeaderButton } from "@/components/ui/Card/Card";
import { Icon } from "@/components/ui/Icon/Icon";
import { Divider } from "@/components/ui/Divider";
import { CardHeader } from "@/components/cards/CardHeader";
import { RelatedTask } from "@/components/cards/RelatedTask";
import { Button } from "@/components/ui/Button/button";
import { useGetTaskByIdQuery } from "@/api/fakeApi";
import { formatDateWithTime, formatDeadline } from "@/helpers/date";
import { statusLabel } from "@/helpers/status";

export type CardTaskProps = {
  taskId: string | null;
  isOpen: boolean;
  onClose: () => void;
  onOpenIncident?: (incidentTitle: string) => void;
};

/* ------------------------------------------------------------------ */
/*  Avatar с инициалами                                                */
/* ------------------------------------------------------------------ */

function Avatar({ name }: { name: string }) {
  const initials = name
    .split(" ")
    .map((w) => w[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);
  return (
    <div className="w-8 h-8 rounded-full bg-(--color-accent-light) text-(--color-accent) flex items-center justify-center text-xs font-semibold shrink-0">
      {initials}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Компонент                                                          */
/* ------------------------------------------------------------------ */
/*  Компонент                                                          */
/* ------------------------------------------------------------------ */

export function CardTask({ taskId, isOpen, onClose, onOpenIncident }: CardTaskProps) {
  const { data: task, isLoading } = useGetTaskByIdQuery(taskId ?? "", {
    skip: !taskId,
  });

  const [showComment, setShowComment] = useState(false);
  const [comment, setComment] = useState("");

  const header = useMemo(() => {
    if (!task) return null;
    return (
      <CardHeader
        priority={task.priority}
        status={statusLabel(task.status)}
        dateLabel="Создана"
        dateValue={formatDateWithTime(task.createdAt)}
        title={task.incidentId}
        tags={[task.object, task.category, task.type]}
      />
    );
  }, [task]);

  const headerButtons: CardHeaderButton[] = useMemo(() => {
    return [
      {
        icon: <Icon name="arrow-right" />,
        onClick: onClose,
        label: "Назад",
      },
    ];
  }, [onClose]);

  const handleAddComment = useCallback(() => {
    if (!comment.trim()) return;
    // TODO: useAddCommentMutation
    setComment("");
    setShowComment(false);
  }, [comment]);

  if (!taskId) return null;

  if (isLoading) {
    return (
      <Card
        isOpen={isOpen}
        onClose={onClose}
        header={<div className="text-sm text-(--color-muted)">Загрузка...</div>}
        onCopyLink={() => {}}
        onOpenSource={() => {}}
      >
        <div className="p-4 text-sm text-(--color-muted)">Загрузка...</div>
      </Card>
    );
  }

  if (!task) {
    return (
      <Card
        isOpen={isOpen}
        onClose={onClose}
        header={<div className="text-sm text-(--color-muted)">Задача не найдена</div>}
        onCopyLink={() => {}}
        onOpenSource={() => {}}
      >
        <div className="p-4 text-sm text-(--color-muted)">Задача не найдена</div>
      </Card>
    );
  }

  return (
    <Card
      isOpen={isOpen}
      onClose={onClose}
      header={header}
      headerButtons={headerButtons}
      onCopyLink={() => {}}
      onOpenSource={() => {}}
    >
      {/* ── Требуемое действие ── */}
      <div className="space-y-4">
        <p className="text-[13px] font-semibold text-(--color-strong)">
          Требуемое действие
        </p>
        <p className="text-xs text-(--color-ink)">{task.action}</p>
      </div>

      <Divider />

      {/* ── Ответственный и срок ── */}
      <div className="space-y-4">
        <p className="text-[13px] font-semibold text-(--color-strong)">
          Ответственный и срок
        </p>
        <div className="flex items-center gap-3">
          <Avatar name={task.assigneeName} />
          <div className="flex flex-col">
            <span className="text-sm font-medium text-(--color-ink)">
              {task.assigneeName}
            </span>
            <span className="text-xs text-(--color-muted)">
              {task.assigneeRole}
            </span>
          </div>
        </div>
        <div className="grid grid-cols-[160px_1fr] gap-x-4 gap-y-3">
          <p className="text-xs text-(--color-muted)">Срок</p>
          <p className="text-xs font-medium text-(--color-ink)">
            {formatDeadline(task.deadline)}
          </p>
        </div>
      </div>

      <Divider />

      {/* ── Ожидаемый результат ── */}
      <div className="space-y-4">
        <p className="text-[13px] font-semibold text-(--color-strong)">
          Ожидаемый результат
        </p>
        <p className="text-xs text-(--color-ink)">{task.expectedResult}</p>
      </div>

      <Divider />

      {/* ── Связанное событие ── */}
      <RelatedTask
        label="Связанное событие"
        description={task.incidentDescription}
        title={task.incidentTitle}
        details={`${task.object} · ${task.category} · ${task.type} · ${task.incidentPriority} · ${task.incidentDate} · ${task.incidentSource}`}
        onClick={() => onOpenIncident?.(task.incidentId)}
      />

      <Divider />

      {/* ── Комментарии и история ── */}
      <div className="text-sm">
        <p className="font-medium">Комментарии и история</p>
        <div className="mb-3">
          {task.history.map((item, i) => (
            <div key={i} className="p-2 rounded-lg">
              <span className="text-xs text-(--color-secondary)">
                {formatDateWithTime(item.createdAt)} · {item.text}
              </span>
            </div>
          ))}
        </div>
        {showComment ? (
          <div>
            <p className="text-(--color-secondary) mb-2">Комментарий аналитика</p>
            <textarea
              className="w-full border border-(--color-border) rounded-lg p-3 text-xs resize-none focus:outline-none focus:border-(--color-accent) bg-transparent"
              rows={3}
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              placeholder="Введите комментарий..."
            />
            <div className="flex gap-2 mt-2">
              <Button
                variant="primary"
                size="small"
                onClick={handleAddComment}
              >
                Отправить
              </Button>
              <Button
                variant="tertiary"
                size="small"
                onClick={() => {
                  setShowComment(false);
                  setComment("");
                }}
              >
                Отмена
              </Button>
            </div>
          </div>
        ) : (
          <button
            onClick={() => setShowComment(true)}
            className="text-(--color-accent) text-sm cursor-pointer bg-transparent border-none p-0 text-left"
          >
            + Комментарий аналитика
          </button>
        )}
      </div>

      <Divider />

      {/* ── Footer ── */}
      <div className="flex justify-end">
        <Button variant="secondary" size="medium">
          Изменить задачу
        </Button>
      </div>
    </Card>
  );
}