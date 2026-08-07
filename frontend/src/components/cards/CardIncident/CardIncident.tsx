"use client";

import { useMemo, useState, useCallback, useEffect, useRef } from "react";
import { useSelector } from "react-redux";
import { Button } from "@/components/ui/Button/button";
import { useCreateActionItemMutation, useGetActionItemsQuery } from "@/api/actionApi";
import { Divider } from "@/components/ui/Divider";
import { TaskCreation } from "@/components/cards/TaskCreation";
import { Attributes } from "@/components/cards/Attributes";
import { RelatedTask } from "@/components/cards/RelatedTask";
import { CommentHistory } from "@/components/cards/CommentHistory";
import { Sources } from "@/components/cards/Sources";
import { Notification } from "@/components/ui/Notification";
import { CardHeader } from "@/components/cards/CardHeader";
import type { Showcase } from "@/api/showcaseApi";
import { Card, CardHeaderButton } from "@/components/ui/Card/Card";
import { Icon } from "@/components/ui/Icon/Icon";
import { statusLabel } from "@/helpers/status";
import { hasAccess, selectUser } from "@/store/authSlice";
import styles from "./CardIncident.module.css";

export type CardIncidentProps = {
  incident: Showcase | null;
  isOpen: boolean;
  onClose: () => void;
  onOpenTask?: (taskId: number) => void;
  onTaskCreated?: (taskId: number) => void;
};

type NotificationState = {
  type: "success" | "error";
  message: string;
} | null;

export function CardIncident({
  incident,
  isOpen,
  onClose,
  onOpenTask,
  onTaskCreated,
}: CardIncidentProps) {
  const [notification, setNotification] = useState<NotificationState>(null);
  const notificationTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [createTask, { isLoading: taskLoading }] = useCreateActionItemMutation();

  const user = useSelector(selectUser);
  const canCreateTask = hasAccess(user?.role, ["admin"]);
  // ! Тут идёт запрос не на события а на задачи с фильтром по showcase_event_id
  const { data: relatedTasks = [] } = useGetActionItemsQuery(
    incident ? { showcase_event_id: incident.id } : undefined,
    { skip: !incident },
  );
  const relatedTask = relatedTasks[0] ?? null;
  const hasTask = !!relatedTask;

  useEffect(() => {
    return () => {
      if (notificationTimerRef.current) clearTimeout(notificationTimerRef.current);
    };
  }, []);

  const handleTaskSuccess = useCallback(
    (createdTaskId: number) => {
      setNotification({
        type: "success",
        message: "Задача успешно создана, событие передано в работу",
      });
      onTaskCreated?.(createdTaskId);
      if (notificationTimerRef.current) clearTimeout(notificationTimerRef.current);
      notificationTimerRef.current = setTimeout(() => setNotification(null), 3000);
    },
    [onTaskCreated],
  );

  const handleTaskError = useCallback(() => {
    setNotification({ type: "error", message: "Задача не создана, ошибка" });
    if (notificationTimerRef.current) clearTimeout(notificationTimerRef.current);
    notificationTimerRef.current = setTimeout(() => setNotification(null), 3000);
  }, []);

  const headerButtons: CardHeaderButton[] = useMemo(() => {
    if (!relatedTask) return [];
    return [
      {
        icon: <Icon name="arrow-right" />,
        onClick: () => onOpenTask?.(relatedTask.id),
        label: "Открыть задачу",
      },
    ];
  }, [relatedTask, onOpenTask]);

  const header = useMemo(() => {
    if (!incident) return null;
    return (
      <CardHeader
        priority={incident.priority}
        status="Новое"
        dateLabel="Обнаружено"
        dateValue={incident.published_at.slice(0, 10).split("-").reverse().join(".")}
        title={incident.title}
        tags={[
          <span key="object">
            <span className={styles.label}>Объект</span>{" "}
            <span className={styles.value}>{incident.competitor}</span>
          </span>,
          <span key="category">
            <span className={styles.label}>Категория</span>{" "}
            <span className={styles.value}>{incident.category}</span>
          </span>,
          <span key="region">
            <span className={styles.label}>Регион</span>{" "}
            <span className={styles.value}>{incident.region}</span>
          </span>,
        ]}
      />
    );
  }, [incident]);

  if (!incident) return null;
  return (
    <Card
      isOpen={isOpen}
      onClose={onClose}
      header={header}
      headerButtons={headerButtons}
      onCopyLink={() => {
        const url = `${window.location.origin}/incidents/${incident.id}`;
        navigator.clipboard.writeText(url).then(() => {
          setNotification({ type: "success", message: "Ссылка на событие скопирована" });
          if (notificationTimerRef.current) clearTimeout(notificationTimerRef.current);
          notificationTimerRef.current = setTimeout(() => setNotification(null), 3000);
        });
      }}
      onOpenSource={() => {
        if (incident.source_url) {
          window.open(incident.source_url, "_blank", "noopener,noreferrer");
        }
      }}
    >
      <div className="space-y-2">
        <p className="text-[13px] font-semibold text-(--color-strong)">Что произошло</p>
        <p className="text-xs text-(--color-ink)">{incident.title}</p>
      </div>
      <Divider />
      <div className="space-y-2">
        <p className="text-[13px] font-semibold text-(--color-strong)">Анализ события</p>
        <div className="grid grid-cols-[160px_1fr] gap-x-4 gap-y-3">
          <p className="text-xs text-(--color-muted)">Комментарий</p>
          <p className="text-xs text-(--color-ink)">
            {incident.comment ? incident.comment : 'Комментарий отсутствует'}
          </p>
          <p className="text-xs text-(--color-muted)">Рекомендуемое действие</p>
          <p className="text-xs text-(--color-ink)">
            {incident.action ? incident.action : 'Рекомендации отсутствуют'}
          </p>
          <p className="text-xs text-(--color-muted)">Срок реакции</p>
          <p className="text-xs font-medium text-(--color-ink)">
          {incident.deadline ? incident.deadline : 'Срок не определён'}</p>
        </div>
      </div>

      <Divider />
      {hasTask && relatedTask ? (
        <>
          <RelatedTask
            title={relatedTask.title}
            details={`${statusLabel(relatedTask.status)}${relatedTask.deadline ? ` · до ${relatedTask.deadline.slice(0, 10)}` : ""}`}
            onClick={() => onOpenTask?.(relatedTask.id)}
          />
          <Divider />
        </>
      ) : canCreateTask ? (
        <TaskCreation
          incidentId={incident.id}
          onSubmit={(data) => createTask(data).unwrap()}
          onSuccess={(created) => handleTaskSuccess(created.id)}
          onError={handleTaskError}
        />
      ) : (
        <p className="text-xs text-(--color-muted)">
          Задача по событию ещё не создана. Создание задач доступно только администраторам.
        </p>
      )}
      {notification && (
        <div className="fixed top-4 left-1/2 -translate-x-1/2 z-50">
          <Notification type={notification.type}>{notification.message}</Notification>
        </div>
      )}
      <Divider />
      <Sources
        source={incident.source_url}
        items={[
          { name: `${incident.media}`, date: "26 июл 2026", label: "первоисточник" },
        ]}
      />
      <Divider />
      {/* пока нет необходимости */}
      {/* <CommentHistory
        items={[
          "10:42 · Событие создано из публикации РБК",
          "10:42 · Событие создано из публикации РБК",
        ]}
      /> */}
    </Card>
  );
}