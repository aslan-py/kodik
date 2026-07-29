"use client";

import Button from "@/components/ui/Button/button";
import { DateInput } from "@/components/inputs/DateInput";
import { TextInput } from "@/components/inputs/TextInput";
import { Divider } from "@/components/ui/Divider";
import { Select, SelectItem } from "@/components/ui/Select";
import type { IncidentItem } from "@/types/types";
import { Card } from "@ui/Card/Card";

type CardIncidentProps = {
  incident: IncidentItem | null;
  isOpen: boolean;
  onClose: () => void;
};

export function CardIncident({ incident, isOpen, onClose }: CardIncidentProps) {
  return (
    <Card
      isOpen={isOpen}
      onClose={onClose}
      header={
        <div className="flex items-center justify-between w-full">
          <div className="flex flex-col gap-1">
            <p>
              <span>П1</span>
              <span>Новое</span>
              <span>Обнаружено 26 июл, 09:18</span>
            </p>
            <h2 className="text-lg font-semibold m-0 text-[#111827]">
              Wildberries запускает экспресс-доставку для региональных продавцов
            </h2>
            <Divider />
            <div className="flex items-center gap-3 text-xs text-[#6b7280]">
              <p>Объект Wildberries · Маркетплейсы · Доставка</p>
            </div>
          </div>
        </div>
      }
    >
      {/* {incident && ( */}
      <div className="space-y-4 text-sm">
        <p>Что произошло</p>
        
        <p>
          Wildberries запустил экспресс-доставку для региональных продавцов,
          чтобы ускорить вывод товаров в локальные кластеры. Событие усиливает
          конкуренцию за продавцов вне столичных регионов и может повлиять на
          ожидания по скорости доставки на маркетплейсах.
        </p>
      </div>
      <div className="space-y-4 text-sm">
        <p>Анализ события</p>
        <div className="flex">
          <p>Причина приоритета</p>
          <p>
            Изменение логистического сервиса конкурента с прямым влиянием на
            продавцов и региональный SLA.
          </p>
        </div>
        <div className="flex">
          <p>Причина приоритета</p>
          <p>
            Изменение логистического сервиса конкурента с прямым влиянием на
            продавцов и региональный SLA.
          </p>
        </div>
        <div className="flex">
          <p>Причина приоритета</p>
          <p>
            Изменение логистического сервиса конкурента с прямым влиянием на
            продавцов и региональный SLA.
          </p>
        </div>
        <div className="flex">
          <p>Причина приоритета</p>
          <p>
            Изменение логистического сервиса конкурента с прямым влиянием на
            продавцов и региональный SLA.
          </p>
        </div>
      </div>
      <div className="space-y-4 text-sm">
        <h3>Атрибуты</h3>
        <div className="flex">
          <p>Конкурент / объект</p>
          <p>Wildberries</p>
        </div>
        <div className="flex">
          <p>Категория</p>
          <p>Wildberries</p>
        </div>
        <div className="flex">
          <p>Конкурент / объект</p>
          <p>
            <span className="priority priority-accent">П1</span>
          </p>
        </div>
        <div className="flex">
          <p>Тональность</p>
          <p>
            <span className="tonality tonality-positive">Позитивная</span>.
          </p>
        </div>
        <div className="flex">
          <p>Регион</p>
          <p>Сибирь</p>
        </div>
        <div className="flex">
          <Button variant="badge">Подтвердить разметку</Button>
          <Button variant="badge" badgeColor="gray">
            Исправить
          </Button>
        </div>
      </div>

      <div className="space-y-4 text-sm">
        <p>Создание задачи</p>
        <div>
          <p>Требуемое действие</p>
          <TextInput  multiline width="" height="120px" value="Короткая оценка риска, список ответных действий и рекомендация по коммуникации для селлеров." onChange={() => {}}></TextInput>
        </div>
        <div>
          <p>Ответственный отдел</p>
          <Select className="surface-block interactive-surface" buttonContent={'Выберите отдел'}>
            <SelectItem onClick={() => {}}>Комммерческий отдел </SelectItem>
            <SelectItem onClick={() => {}}>Финансовый отдел </SelectItem>
          </Select>
          <input type="text" name="" id="" />
        </div>
        <div>
          <p>Срок</p>
          <DateInput  value="" onChange={() => {}} />
        </div>
        <div>
          <p>Ожидаемый результат</p>
          {/* инпут селект */}
          <TextInput value="Короткая оценка риска, список ответных действий и рекомендация по коммуникации для селлеров." onChange={() => {}}></TextInput>
        </div>
        <Button className="surface-block interactive-surface justify-start">+  Комментарий</Button>
      </div>
      <div className="space-y-4 text-sm">
        <p>Что произошло</p>
        <p>
          Wildberries запустил экспресс-доставку для региональных продавцов,
          чтобы ускорить вывод товаров в локальные кластеры. Событие усиливает
          конкуренцию за продавцов вне столичных регионов и может повлиять на
          ожидания по скорости доставки на маркетплейсах.
        </p>
      </div>
      <Divider />
    </Card>
  );
}
