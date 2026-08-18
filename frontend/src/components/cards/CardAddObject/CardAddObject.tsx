"use client";

import { useState } from "react";
import { Card } from "@/components/ui/Card/Card";
import { Button } from "@/components/ui/Button/button";
import { Divider } from "@/components/ui/Divider";
import { Input } from "@/components/ui/Input/Input";
import { Icon } from "@/components/ui/Icon/Icon";

export type CardAddObjectProps = {
  type: "competitor" | "source";
  isOpen: boolean;
  onClose: () => void;
};

/* ------------------------------------------------------------------ */
/*  TagInput — поле ввода с добавлением тегов                          */
/* ------------------------------------------------------------------ */

function TagInput({
  tags,
  onAdd,
  onRemove,
  placeholder,
}: {
  tags: string[];
  onAdd: (tag: string) => void;
  onRemove: (tag: string) => void;
  placeholder?: string;
}) {
  const [value, setValue] = useState("");

  const handleAdd = () => {
    const trimmed = value.trim();
    if (!trimmed) return;
    onAdd(trimmed);
    setValue("");
  };

  return (
    <div>
      <div className="flex gap-2 items-center">
        <Input
          id="trigger"
          value={value}
          onChange={setValue}
          placeholder={placeholder ?? "Добавить триггер"}
          width="240px"
          inputProps={{ onKeyDown: (e) => { if (e.key === "Enter") { e.preventDefault(); handleAdd(); } } }}
        />
        <button
          type="button"
          onClick={handleAdd}
          className="flex items-center gap-1 text-xs text-(--color-accent) cursor-pointer bg-transparent border-none p-0 whitespace-nowrap"
        >
          <Icon name="add" /> Добавить триггер
        </button>
      </div>
      {tags.length > 0 && (
        <div className="flex flex-wrap gap-2 mt-2">
          {tags.map((tag) => (
            <span
              key={tag}
              className="inline-flex items-center gap-1 text-xs px-2.5 py-1 rounded-full bg-(--color-accent-light) text-(--color-accent)"
            >
              {tag}
              <button
                type="button"
                onClick={() => onRemove(tag)}
                className="text-(--color-accent) cursor-pointer bg-transparent border-none p-0 leading-none text-sm"
              >
                ×
              </button>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Основной компонент                                                 */
/* ------------------------------------------------------------------ */

export function CardAddObject({ type, isOpen, onClose }: CardAddObjectProps) {
  const [name, setName] = useState("");
  const [region, setRegion] = useState("");
  const [comment, setComment] = useState("");
  const [triggers, setTriggers] = useState<string[]>([
    "Wildberries",
    "Вайлдберриз",
    "экспресс-доставка",
    "региональные продавцы",
  ]);

  // Для источника
  const [sourceUrl, setSourceUrl] = useState("");
  const [accessType, setAccessType] = useState("Открытый / бесплатный API");
  const [apiUrl, setApiUrl] = useState("");
  const [authMethod, setAuthMethod] = useState("Bearer token");
  const [token, setToken] = useState("");
  const [rateLimit, setRateLimit] = useState("");

  const handleAddTrigger = (tag: string) => {
    if (!triggers.includes(tag)) {
      setTriggers([...triggers, tag]);
    }
  };

  const handleRemoveTrigger = (tag: string) => {
    setTriggers(triggers.filter((t) => t !== tag));
  };

  const handleSubmit = () => {
    // TODO: мутация
    onClose();
  };

  const title = type === "competitor" ? "Добавить конкурента" : "Добавить источник";
  const subtitle =
    type === "competitor"
      ? "Настройте объект мониторинга и поисковые триггеры."
      : "Настройте источник и параметры подключения.";
  const submitLabel = type === "competitor" ? "Добавить конкурента" : "Добавить источник";

  return (
    <Card
      isOpen={isOpen}
      onClose={onClose}
      header={
        <div className="flex flex-col">
          <h2 className="text-2xl font-semibold text-(--color-strong) m-0">{title}</h2>
          <p className="text-xs text-(--color-muted) mt-1">{subtitle}</p>
          <Divider />
        </div>
      }
    >
      {type === "competitor" ? (
        /* ─────────── КОНКУРЕНТ ─────────── */
        <div className="space-y-4">
          {/* Основная информация */}
          <p className="text-[13px] font-semibold text-(--color-strong)">Основная информация</p>

          <div className="space-y-3">
            <div>
              <p className="text-xs text-(--color-muted) mb-1.5">
                Название конкурента <span className="text-(--color-accent)">*</span>
              </p>
              <Input id="name" value={name} onChange={setName} placeholder="Введите название" />
            </div>

            <div>
              <p className="text-xs text-(--color-muted) mb-1.5">Регион</p>
              <Input id="region" value={region} onChange={setRegion} placeholder="Выберите один или несколько регионов" />
            </div>

            <div>
              <p className="text-xs text-(--color-muted) mb-1.5">Комментарий (необязательно)</p>
              <Input id="comment"
                multiline
                value={comment}
                onChange={setComment}
                placeholder="Добавьте внутреннюю заметку"
                inputClassName="py-3"
              />
            </div>
          </div>

          <Divider />

          {/* Триггеры */}
          <p className="text-[13px] font-semibold text-(--color-strong)">Триггеры</p>
          <TagInput
            tags={triggers}
            onAdd={handleAddTrigger}
            onRemove={handleRemoveTrigger}
            placeholder="Например, экспресс-доставка"
          />
          <p className="text-xs text-(--color-muted)">
            Система использует триггеры для формирования поисковых запросов по подключённым источникам.
          </p>

          <Divider />

          {/* Footer */}
          <div className="flex justify-end gap-2.5">
            <Button variant="secondary" onClick={onClose}>Отмена</Button>
            <Button variant="primary" onClick={handleSubmit}>{submitLabel}</Button>
          </div>
        </div>
      ) : (
        /* ─────────── ИСТОЧНИК ─────────── */
        <div className="space-y-4">
          {/* Основная информация */}
          <p className="text-[13px] font-semibold text-(--color-strong)">Основная информация</p>

          <div className="space-y-3">
            <div>
              <p className="text-xs text-(--color-muted) mb-1.5">
                Название источника <span className="text-(--color-accent)">*</span>
              </p>
              <Input id="name" value={name} onChange={setName} placeholder="Введите название" />
            </div>

            <div>
              <p className="text-xs text-(--color-muted) mb-1.5">
                Тип доступа <span className="text-(--color-accent)">*</span>
              </p>
              <Input id="accessType"
                value={accessType}
                onChange={setAccessType}
                placeholder="Открытый / бесплатный API"
              />
            </div>

            <div>
              <p className="text-xs text-(--color-muted) mb-1.5">
                URL источника <span className="text-(--color-accent)">*</span>
              </p>
              <Input id="sourceUrl" value={sourceUrl} onChange={setSourceUrl} placeholder="https://" />
            </div>

            <div>
              <p className="text-xs text-(--color-muted) mb-1.5">Комментарий</p>
              <Input id="comment"
                multiline
                value={comment}
                onChange={setComment}
                placeholder="Добавьте внутреннюю заметку"
                inputClassName="py-3"
              />
            </div>
          </div>

          <Divider />

          {/* Параметры подключения */}
          <p className="text-[13px] font-semibold text-(--color-strong)">Параметры подключения</p>

          <div className="space-y-3">
            <div>
              <p className="text-xs text-(--color-muted) mb-1.5">URL API / endpoint</p>
              <Input id="apiUrl" value={apiUrl} onChange={setApiUrl} placeholder="https://api.example.ru/v1" />
            </div>

            <div>
              <p className="text-xs text-(--color-muted) mb-1.5">Способ авторизации</p>
              <Input id="authMethod" value={authMethod} onChange={setAuthMethod} placeholder="Bearer token" />
            </div>

            <div>
              <p className="text-xs text-(--color-muted) mb-1.5">Ключ или токен доступа</p>
              <Input id="token"
                value={token}
                onChange={setToken}
                placeholder="Введите секретное значение"
              />
            </div>

            <div>
              <p className="text-xs text-(--color-muted) mb-1.5">Лимит запросов (необязательно)</p>
              <Input id="rateLimit" value={rateLimit} onChange={setRateLimit} placeholder="Не задан" />
            </div>
          </div>

          <p className="text-xs text-(--color-muted)">
            Параметры настраиваются техническим специалистом после модерации.
          </p>

          <Divider />

          {/* Footer */}
          <div className="flex justify-end gap-2.5">
            <Button variant="secondary" onClick={onClose}>Отмена</Button>
            <Button variant="primary" onClick={handleSubmit}>{submitLabel}</Button>
          </div>
        </div>
      )}
    </Card>
  );
}