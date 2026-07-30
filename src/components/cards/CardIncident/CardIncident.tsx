"use client";

import { useMemo } from "react";
import Button from "@/components/ui/Button/button";
import { Divider } from "@/components/ui/Divider";
import { TagList } from "@/components/ui/TagList";
import { TaskCreation } from "@/components/cards/TaskCreation";
import { Attributes } from "@/components/cards/Attributes";
import { RelatedTask } from "@/components/cards/RelatedTask";
import type { IncidentItem } from "@/types/types";
import { Card } from "@/components/ui/Card/Card";
import { Icon } from "@/components/ui/Icon/Icon";
import { DeadlineState } from "@/components/ui/DeadlineState";

type CardIncidentProps = {
  incident: IncidentItem | null;
  isOpen: boolean;
  onClose: () => void;
};

export function CardIncident({ incident, isOpen, onClose }: CardIncidentProps) {
  if (!incident) return null;

  const header = useMemo(() => (
    <div className="flex items-center justify-between w-full">
          <div className="flex flex-col">
            <p className="flex gap-[10px] mb-[14px] items-center">
              <span className="priority priority-accent">{incident.priority}</span>
              <span className="tonality tonality-neutral">Новое</span>
              <span className="text-xs text-[var(--color-muted)]">Обнаружено {incident.data}</span>
            </p>
            <h2 className="text-2xl font-semibold text-[var(--color-strong)] mb-[14px] m-0">
              {incident.incident}
            </h2>
            <div className="text-xs text-[var(--color-muted)]">
              Объект <span className="text-[var(--color-ink)]">{incident.object}</span> · {incident.category} · {incident.type}
            </div>
            <Divider />
          </div>
        </div>
  ), [incident]);

  return (
    <Card
      isOpen={isOpen}
      onClose={onClose}
      header={header}
    >

      <div className="space-y-4">
        <p className="text-[13px] font-semibold text-[var(--color-strong)]">Что произошло</p>
        <p className="text-xs text-[var(--color-ink)]">
          Wildberries запустил экспресс-доставку для региональных продавцов,
          чтобы ускорить вывод товаров в локальные кластеры. Событие усиливает
          конкуренцию за продавцов вне столичных регионов и может повлиять на
          ожидания по скорости доставки на маркетплейсах.
        </p>
      </div>
      <Divider></Divider>
      <div className="space-y-4">
        <p className="text-[13px] font-semibold text-[var(--color-strong)]">Анализ события</p>
        <div className="grid grid-cols-[160px_1fr] gap-x-4 gap-y-3">
          <p className="text-xs text-[var(--color-muted)]">Причина приоритета</p>
          <p className="text-xs text-[var(--color-ink)]">
            Изменение логистического сервиса конкурента с прямым влиянием на
            продавцов и региональный SLA.
          </p>
          <p className="text-xs text-[var(--color-muted)]">Риск / возможность</p>
          <p className="text-xs text-[var(--color-ink)]">
            Риск перетока региональных продавцов; возможность усилить собственные условия доставки и коммуникацию для селлеров.
          </p>
          <p className="text-xs text-[var(--color-muted)]">Рекомендуемое действие</p>
          <p className="text-xs text-[var(--color-ink)]">
            Передать событие в коммерческий и логистический блоки для оценки реакции по региональным продавцам.
          </p>
          <p className="text-xs text-[var(--color-muted)]">Срок реакции</p>
          <p className="text-xs font-medium text-[var(--color-ink)]">
            До конца рабочего дня
          </p>
        </div>
      </div>
      <Divider></Divider>
      <Attributes incident={incident} onConfirm={() => console.log("подтверждено")}
  onFix={() => console.log("исправить")} />
      <Divider />
      <TaskCreation />
      <Divider></Divider>
      <RelatedTask />
      <Divider></Divider>
      <div className="space-y-4 text-sm">
        <p>Источники</p>
        <TagList
          items={[
            <span>Основной источник: {incident.source}</span>,
            <span>{incident.source}</span>,
          ]}
        />
        <div>
          <ul>
            <li>
              <div>
                <div className="flex justify-between">
                  <div className="flex flex-col">
                    <span>Коммерсантъ</span>
                    <div>
                      <span>26 июл 2026</span> · <span>первоисточник</span>{" "}
                    </div>
                  </div>
                  <Button
                    endIcon={<Icon name="link" />}
                    variant="link"
                    className=""
                  ></Button>
                </div>
              </div>
            </li>
            <li>
              <div>
                <div className="flex justify-between">
                  <div className="flex flex-col">
                    <span>Коммерсантъ</span>
                    <div>
                      <span>26 июл 2026</span> · <span>первоисточник</span>{" "}
                    </div>
                  </div>
                  <Button
                    endIcon={<Icon name="link" />}
                    variant="link"
                    className=""
                  ></Button>
                </div>
              </div>
            </li>
          </ul>
        </div>
      </div>
      <Divider />
      <div className="space-y-4 text-sm">
        <h3>Комментарии и история</h3>
        <ul>
          <li>
            <div className="flex">
              <span>10:42</span> · <p>Событие создано из публикации РБК</p>
            </div>
          </li>
          <li>
            <div className="flex">
              <span>10:42</span> · <p>Событие создано из публикации РБК</p>
            </div>
          </li>
        </ul>
        <Button>+  Комментарий аналитика</Button>
      </div>
      <Divider />
      <div className="space-y-4 text-sm">
          <span>Событие не обработано</span>
          <div>
            <Button>Отметить шум</Button>
            <Button>Создать задачу</Button>
          </div>
      </div>
    </Card>
  );
}
