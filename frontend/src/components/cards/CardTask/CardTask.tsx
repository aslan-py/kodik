"use client";

import { useCallback, useMemo, useState } from "react";
import { Card, CardHeaderButton } from "@/components/ui/Card/Card";
import { Icon } from "@/components/ui/Icon/Icon";
import { Divider } from "@/components/ui/Divider";
import { CardHeader } from "@/components/cards/CardHeader";
import { RelatedTask } from "@/components/cards/RelatedTask";
import { Button } from "@/components/ui/Button/button";
import { useGetActionItemByIdQuery } from "@/api/actionApi";
import { useGetShowcaseByIdQuery } from "@/api/showcaseApi";
import { formatDateWithTime, formatDeadline } from "@/helpers/date";
import { statusLabel } from "@/helpers/status";
import Loader from "@/app/loading";

export type CardTaskProps = {
  taskId: number | null;
  isOpen: boolean;
  onClose: () => void;
  onOpenIncident: (incidentId: number) => void;
};

const cardStubProps = {
  onCopyLink: () => {},
  onOpenSource: () => {},
};

export function CardTask({ taskId, isOpen, onClose, onOpenIncident }: CardTaskProps) {
  const { data: task, isLoading } = useGetActionItemByIdQuery(taskId ?? 0, {
    skip: !taskId,
  });

  // связанное событие подтягиваем отдельно по showcase_id, когда задача загружена
  const { data: incident } = useGetShowcaseByIdQuery(task?.showcase_id ?? 0, {
    skip: !task,
  });

  const [showComment, setShowComment] = useState(false);
  const [comment, setComment] = useState("");

  const header = useMemo(() => {
    if (!task) return null;
    return (
      <CardHeader
        priority={incident?.priority ?? ""}
        status={statusLabel(task.status)}
        dateLabel="Создана"
        dateValue={formatDateWithTime(task.created_at)}
        title={task.title}
        tags={[incident?.competitor, incident?.category].filter(Boolean) as string[]}
      />
    );
  }, [task, incident]);

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
    // TODO: подключить, когда появится API комментариев/истории задачи
    setComment("");
    setShowComment(false);
  }, [comment]);

  if (!taskId) return null;

  if (isLoading) {
    return (
      <Card
        isOpen={isOpen}
        onClose={onClose}
        header={<Loader />}
        {...cardStubProps}
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
        {...cardStubProps}
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
      {...cardStubProps}
    >
      {/* ── Требуемое действие ── */}
      <div className="space-y-4">
        <p className="text-[13px] font-semibold text-(--color-strong)">
          Требуемое действие
        </p>
        <p className="text-xs text-(--color-ink)">{task.title}</p>
      </div>

      <Divider />

      {/* ── Ответственный и срок ── */}
      <div className="space-y-4">
        <p className="text-[13px] font-semibold text-(--color-strong)">
          Ответственный и срок
        </p>
        {/* TODO: заглушка — заменить на данные пользователя, когда появится usersApi */}
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-(--color-accent-light) text-(--color-accent) flex items-center justify-center text-xs font-semibold shrink-0">
            —
          </div>
          <div className="flex flex-col">
            <span className="text-sm font-medium text-(--color-ink)">
              {task.assigned_user_id != null
                ? `Пользователь #${task.assigned_user_id}`
                : "Не назначен"}
            </span>
          </div>
        </div>
        <div className="grid grid-cols-[160px_1fr] gap-x-4 gap-y-3">
          <p className="text-xs text-(--color-muted)">Срок</p>
          <p className="text-xs font-medium text-(--color-ink)">
            {task.deadline ? formatDeadline(task.deadline) : "—"}
          </p>
        </div>
      </div>

      <Divider />

      {/* ── Ожидаемый результат ── */}
      <div className="space-y-4">
        <p className="text-[13px] font-semibold text-(--color-strong)">
          Ожидаемый результат
        </p>
        <p className="text-xs text-(--color-ink)">{task.expected_result}</p>
      </div>

      <Divider />

      {/* ── Связанное событие ── */}
      {incident && (
        <RelatedTask
          label="Связанное событие"
          description={incident.title}
          title={incident.title}
          details={`${incident.competitor} · ${incident.category} · ${incident.priority} · ${incident.published_at.slice(0, 10)} · ${incident.region}`}
          onClick={() => onOpenIncident(task.showcase_id)}
        />
      )}

      <Divider />

      {/* ── Комментарии и история ── */}
      {/* TODO: заглушка — подключить, когда появится API истории/комментариев задачи */}
      <div className="text-sm">
        <p className="font-medium">Комментарии и история</p>
        <div className="mb-3 text-xs text-(--color-muted)">Пока недоступно</div>
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
              <Button variant="primary" size="small" onClick={handleAddComment}>
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