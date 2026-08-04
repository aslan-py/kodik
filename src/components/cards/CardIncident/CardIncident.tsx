"use client";

import { useMemo, useState, useCallback, useEffect, useRef } from "react";
import { Button } from "@/components/ui/Button/button";
import { useCreateTaskMutation } from "@/api/fakeApi";
import { Divider } from "@/components/ui/Divider";
import { TaskCreation } from "@/components/cards/TaskCreation";
import { Attributes } from "@/components/cards/Attributes";
import { RelatedTask } from "@/components/cards/RelatedTask";
import { CommentHistory } from "@/components/cards/CommentHistory";
import { Sources } from "@/components/cards/Sources";
import { Notification } from "@/components/ui/Notification";
import { CardHeader } from "@/components/cards/CardHeader";
import type { IncidentItem } from "@/types/types";
import { Card, CardHeaderButton } from "@/components/ui/Card/Card";
import { Icon } from "@/components/ui/Icon/Icon";

export type CardIncidentProps = {
  incident: IncidentItem | null;
  isOpen: boolean;
  onClose: () => void;
  onOpenTask?: (taskId: string) => void;
  onTaskCreated?: (taskId: string) => void;
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
  const [createTask, { isLoading: taskLoading }] = useCreateTaskMutation();

  useEffect(() => {
    return () => {
      if (notificationTimerRef.current) clearTimeout(notificationTimerRef.current);
    };
  }, []);

  const hasTask = !!incident?.taskId;

  const handleTaskSuccess = useCallback(() => {
    setNotification({
      type: "success",
      message: "Задача успешно создана, событие передано в работу",
    });
    onTaskCreated?.(`task-${Date.now()}`);
    if (notificationTimerRef.current) clearTimeout(notificationTimerRef.current);
    notificationTimerRef.current = setTimeout(() => setNotification(null), 3000);
  }, [onTaskCreated]);

  const handleTaskError = useCallback(() => {
    setNotification({
      type: "error",
      message: "Задача не создана, ошибка",
    });
    if (notificationTimerRef.current) clearTimeout(notificationTimerRef.current);
    notificationTimerRef.current = setTimeout(() => setNotification(null), 3000);
  }, []);

  const headerButtons: CardHeaderButton[] = useMemo(() => {
    if (!hasTask || !incident?.taskId) return [];
    return [
      {
        icon: <Icon name="arrow-right" />,
        onClick: () => onOpenTask?.(incident.taskId!),
        label: "Открыть задачу",
      },
    ];
  }, [hasTask, incident, onOpenTask]);

  const header = useMemo(() => {
    if (!incident) return null;
    return (
      <CardHeader
        priority={incident.priority}
        status="Новое"
        dateLabel="Обнаружено"
        dateValue={incident.data}
        title={incident.incident}
        tags={[`Объект ${incident.object}`, incident.category, incident.type]}
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
        /* копировать ссылку */
      }}
      onOpenSource={() => {
        /* открыть источник */
      }}
    >
      <div className="space-y-4">
        <p className="text-[13px] font-semibold text-(--color-strong)">
          Что произошло
        </p>
        <p className="text-xs text-(--color-ink)">
          Wildberries запустил экспресс-доставку для региональных продавцов,
          чтобы ускорить вывод товаров в локальные кластеры. Событие усиливает
          конкуренцию за продавцов вне столичных регионов и может повлиять на
          ожидания по скорости доставки на маркетплейсах.
        </p>
      </div>
      <Divider></Divider>
      <div className="space-y-4">
        <p className="text-[13px] font-semibold text-(--color-strong)">
          Анализ события
        </p>
        <div className="grid grid-cols-[160px_1fr] gap-x-4 gap-y-3">
          <p className="text-xs text-(--color-muted)">Причина приоритета</p>
          <p className="text-xs text-(--color-ink)">
            Изменение логистического сервиса конкурента с прямым влиянием на
            продавцов и региональный SLA.
          </p>
          <p className="text-xs text-(--color-muted)">Риск / возможность</p>
          <p className="text-xs text-(--color-ink)">
            Риск перетока региональных продавцов; возможность усилить
            собственные условия доставки и коммуникацию для селлеров.
          </p>
          <p className="text-xs text-(--color-muted)">Рекомендуемое действие</p>
          <p className="text-xs text-(--color-ink)">
            Передать событие в коммерческий и логистический блоки для оценки
            реакции по региональным продавцам.
          </p>
          <p className="text-xs text-(--color-muted)">Срок реакции</p>
          <p className="text-xs font-medium text-(--color-ink)">
            До конца рабочего дня
          </p>
        </div>
      </div>
      <Divider></Divider>
      <Attributes
        incident={incident}
        onConfirm={() => console.log("подтверждено")}
        onFix={() => console.log("исправить")}
      />
      <Divider />
      {hasTask ? (
        <>
          <RelatedTask
            title="Оценить влияние экспресс-доставки Wildberries"
            details="Коммерческий отдел · сегодня 18:00 · В работе"
            onClick={() => onOpenTask?.(incident.taskId!)}
          />
          <Divider />
        </>
      ) : (
        <>
          <TaskCreation
            incidentId={incident.incident}
            onSubmit={(data) => createTask(data).unwrap()}
            onSuccess={handleTaskSuccess}
            onError={handleTaskError}
          />
        </>
      )}
      {notification && (
        <div className="fixed top-4 left-1/2 -translate-x-1/2 z-50">
          <Notification type={notification.type}>
            {notification.message}
          </Notification>
        </div>
      )}
      <Divider />
      <Sources
        source={incident.source}
        items={[
          { name: "Коммерсантъ", date: "26 июл 2026", label: "первоисточник" },
          { name: "Коммерсантъ", date: "26 июл 2026", label: "первоисточник" },
        ]}
      />
      <Divider />
      <CommentHistory
        items={[
          "10:42 · Событие создано из публикации РБК",
          "10:42 · Событие создано из публикации РБК",
        ]}
      />
      <Divider />
      {hasTask ? (
        <div className="flex justify-between items-center text-sm">
          <span className="font-medium text-(--color-ink)">
            Событие в работе
          </span>
          <div className="flex gap-2.5">
            <Button variant="secondary">Отметить шум</Button>
            <Button
              variant="primary"
              onClick={() => onOpenTask?.(incident.taskId!)}
            >
              Открыть задачу
            </Button>
          </div>
        </div>
      ) : (
        <div className="flex justify-between items-center text-sm">
          <span>Событие не обработано</span>
          <div className="flex gap-2.5">
            <Button variant="secondary">Отметить шум</Button>
            <Button
              type="submit"
              form="task-creation-form"
              loading={taskLoading}
            >
              Создать задачу
            </Button>
          </div>
        </div>
      )}
    </Card>
  );
}
