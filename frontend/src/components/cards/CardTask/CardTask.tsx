"use client";

import { useCallback, useMemo, useState, useEffect, useRef } from "react";
import { Card, CardHeaderButton } from "@/components/ui/Card/Card";
import { Icon } from "@/components/ui/Icon/Icon";
import { Divider } from "@/components/ui/Divider";
import { CardHeader } from "@/components/cards/CardHeader";
import { RelatedTask } from "@/components/cards/RelatedTask";
import { Button } from "@/components/ui/Button/button";
import { useGetActionItemByIdQuery } from "@/api/actionApi";
import { useGetShowcaseByIdQuery } from "@/api/showcaseApi";
import { useGetAllUsersQuery } from "@/api/usersApi";
import { formatDateWithTime, toDisplayDate, toDotDate } from "@/helpers/date";
import { statusLabel } from "@/helpers/status";
import Loader from "@/app/loading";
import { TaskCreation } from "../TaskCreation";
import { usePermission } from "@/hooks/useAuth";
import { useDepartmentName } from "@/hooks/useDepartamentName";
import { Notification } from "@/components/ui/Notification";

export type CardTaskProps = {
  taskId: number | null;
  isOpen: boolean;
  onClose: () => void;
  onOpenIncident?: (incidentId: number) => void; // теперь опционален
};

function DepartmentLabel({ departmentId }: { departmentId: number }) {
  const name = useDepartmentName(departmentId);
  return <span>{name}</span>;
}

type NotificationState = {
  type: "success" | "error";
  message: string;
} | null;

export function CardTask({
  taskId,
  isOpen,
  onClose,
  onOpenIncident,
}: CardTaskProps) {
  const { data: task, isLoading } = useGetActionItemByIdQuery(taskId ?? 0, {
    skip: !taskId,
  });

  const { data: incident } = useGetShowcaseByIdQuery(
    task?.showcase_event_id ?? 0,
    {
      skip: !task?.showcase_event_id,
    },
  );
  // TODO добавить пользователя после подключения по айди
  const { data: user } = useGetAllUsersQuery(
    { id: task?.assigned_user_id ?? undefined },
    {
      skip: !task?.assigned_user_id,
    },
  );
  const [isEditing, setIsEditing] = useState(false);
  const canAdmin = usePermission(["analyst", "admin"]);

  const [notification, setNotification] = useState<NotificationState>(null);
  const notificationTimerRef = useRef<ReturnType<typeof setTimeout> | null>(
    null,
  );

  useEffect(() => {
    return () => {
      if (notificationTimerRef.current)
        clearTimeout(notificationTimerRef.current);
    };
  }, []);

  const showNotification = useCallback(
    (state: NonNullable<NotificationState>) => {
      setNotification(state);
      if (notificationTimerRef.current)
        clearTimeout(notificationTimerRef.current);
      notificationTimerRef.current = setTimeout(
        () => setNotification(null),
        3000,
      );
    },
    [],
  );

  const handleCopyLink = useCallback(() => {
    if (!task) return;
    const url = `${window.location.origin}/task/${task.id}`;
    navigator.clipboard
      .writeText(url)
      .then(() => {
        showNotification({
          type: "success",
          message: "Ссылка на задачу скопирована",
        });
      })
      .catch(() => {
        showNotification({
          type: "error",
          message: "Не удалось скопировать ссылку",
        });
      });
  }, [task, showNotification]);

  const handleOpenSource = useCallback(() => {
    if (incident?.source_url) {
      window.open(incident.source_url, "_blank", "noopener,noreferrer");
    }
  }, [incident]);

  const header = useMemo(() => {
    if (!task) return null;
    return (
      <CardHeader
        priority={incident?.priority ?? ""}
        status={statusLabel(task.status)}
        dateLabel="Создана"
        dateValue={formatDateWithTime(task.created_at)}
        title={task.task}
        tags={
          [incident?.competitor, incident?.category].filter(Boolean) as string[]
        }
      />
    );
  }, [task, incident]);

  if (!taskId) return null;

  if (isLoading) {
    return (
      <Card isOpen={isOpen} onClose={onClose} header={<Loader />}>
        <div className="p-4 text-sm text-(--color-muted)">Загрузка...</div>
      </Card>
    );
  }

  if (!task) {
    return (
      <Card
        isOpen={isOpen}
        onClose={onClose}
        header={
          <div className="text-sm text-(--color-muted)">Задача не найдена</div>
        }
      >
        <div className="p-4 text-sm text-(--color-muted)">
          Задача не найдена
        </div>
      </Card>
    );
  }

  // ── Режим редактирования ──
  if (isEditing && canAdmin) {
    return (
      <Card isOpen={isOpen} onClose={onClose} header={header}>
        <TaskCreation
          incidentId={task.showcase_event_id}
          incidentDeadline={incident?.deadline}
          isEditing
          initialData={task}
          onSuccess={() => setIsEditing(false)}
          onError={() => setIsEditing(false)}
        />
      </Card>
    );
  }

  // ── Режим просмотра ──
  return (
    <Card
      isOpen={isOpen}
      onClose={onClose}
      header={header}
      onCopyLink={handleCopyLink}
      onOpenSource={incident?.source_url ? handleOpenSource : undefined}
      footer={
        <p className="text-xs">Обновлено: {toDotDate(task.updated_at)}</p>
      }
    >
      <div className="mb-4">
        <p className="text-[13px] font-semibold text-(--color-strong)">
          Содержание задачи
        </p>
      </div>
      <div className="mb-4">
        <p className="text-[11px] text-(--color-muted) mb-1">
          Требуемое действие
        </p>
        <p className="text-xs text-(--color-ink)">{task.task}</p>
      </div>

      <div className="mb-4">
        <p className="text-[11px] text-(--color-muted) mb-1">
          Ожидаемый результат
        </p>
        <p className="text-xs text-(--color-ink)">{task.expected_result}</p>
      </div>

      <div className="mb-4">
        <p className="text-[11px] text-(--color-muted) mb-1">
          Ответственный отдел
        </p>
        <p className="text-xs text-(--color-ink)">
          <DepartmentLabel departmentId={task.department_id} />
        </p>
      </div>
      {task.assigned_user_id ? (
        <div className="mb-4">
          <p className="text-[11px] text-(--color-muted) mb-1">Исполнитель</p>
          <div className="text-xs text-(--color-ink)">
            <div className="w-8 h-8 rounded-full bg-(--color-accent-light) text-(--color-accent) flex items-center justify-center text-xs font-semibold shrink-0">
              {task.assigned_user_id}
            </div>
          </div>
        </div>
      ) : (
        ""
      )}

      <div className="mb-4">
        <p className="text-[11px] text-(--color-muted) mb-1">Срок</p>
        <p className="text-xs text-(--color-ink)">
          {task.deadline ? toDisplayDate(task.deadline) : "—"}
        </p>
      </div>

      <Divider />

      {incident && (
        <RelatedTask
          label="Связанное событие"
          description={incident.title}
          title={incident.title}
          details={`${incident.competitor} · ${incident.category} · ${incident.priority} · ${incident.published_at.slice(0, 10)} · ${incident.region}`}
          onClick={
            onOpenIncident
              ? () => onOpenIncident(task.showcase_event_id)
              : undefined
          }
        />
      )}

      <Divider />

      {canAdmin && (
        <div className="flex justify-end">
          <Button
            variant="secondary"
            size="medium"
            onClick={() => setIsEditing(true)}
          >
            Изменить задачу
          </Button>
        </div>
      )}

      {notification && (
        <div className="fixed top-4 left-1/2 -translate-x-1/2 z-50">
          <Notification type={notification.type}>
            {notification.message}
          </Notification>
        </div>
      )}
    </Card>
  );
}
