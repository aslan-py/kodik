"use client";

import { useState, useEffect } from "react";
import { createPortal } from "react-dom";
import {
  useFloating,
  autoUpdate,
  offset,
  flip,
  shift,
  type Placement,
} from "@floating-ui/react";

import { DayPicker } from "react-day-picker";

import {
  addMonths,
  subMonths,
  format,
  addDays,
  setHours,
  setMinutes,
  isSameDay,
  startOfDay,
} from "date-fns";

import { ru } from "date-fns/locale";

import { Input } from "@/components/ui/Input/Input";

import styles from "./DatePicker.module.css";
import { Icon } from "../Icon";

type DateTimePickerProps = {
  value?: Date;
  onChange?: (date: Date) => void;
  /** Показывать ли выбор времени. false — только дата */
  withTime?: boolean;
  /**
   * Сторона открытия попапа относительно инпута.
   * Если места не хватает — floating-ui сам переключит на противоположную (flip).
   * По умолчанию "bottom-start" — открытие вниз, как обычный дропдаун.
   */
  placement?: Placement;
  /** Блокировать выбор дат/времени в прошлом. По умолчанию true */
  disablePast?: boolean;
  disabled?: boolean;
};

function generateTimeOptions(startHour = 7, endHour = 0, step = 60) {
  const result: string[] = [];
  let currentHour = startHour;
  let currentMinute = 0;

  while (true) {
    result.push(
      `${String(currentHour).padStart(2, "0")}:${String(currentMinute).padStart(2, "0")}`,
    );

    currentMinute += step;
    if (currentMinute >= 60) {
      currentMinute = 0;
      currentHour++;
    }
    if (currentHour === 24) currentHour = 0;

    if (currentHour === endHour && currentMinute === 0) {
      result.push("00:00");
      break;
    }
  }

  return result;
}

const ALL_TIME_OPTIONS = generateTimeOptions();

export function DateTimePicker({
  value,
  onChange,
  withTime = true,
  placement = "bottom-start",
  disablePast = true,
  disabled = false,
}: DateTimePickerProps) {
  const [open, setOpen] = useState(false);
  const [date, setDate] = useState<Date>(value ?? new Date());
  const [time, setTime] = useState(format(value ?? new Date(), "HH:mm"));
  const [currentMonth, setCurrentMonth] = useState(value ?? new Date());

  const { refs, floatingStyles, isPositioned } = useFloating({
    open,
    onOpenChange: setOpen,
    placement,
    middleware: [offset(4), flip(), shift({ padding: 8 })],
    whileElementsMounted: autoUpdate,
  });

  // синхронизация с внешним value — если родитель поменял/сбросил дату программно
  useEffect(() => {
    if (value) {
      setDate(value);
      setTime(format(value, "HH:mm"));
      setCurrentMonth(value);
    }
  }, [value]);

  // закрытие при клике вне компонента (и вне инпута, и вне портального попапа)
  useEffect(() => {
    if (!open) return;

    const handler = (e: MouseEvent) => {
      const target = e.target as Node;
      const insideReference =
        refs.reference.current instanceof Element &&
        refs.reference.current.contains(target);
      const insideFloating = refs.floating.current?.contains(target);
      if (!insideReference && !insideFloating) {
        setOpen(false);
      }
    };

    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open, refs.reference, refs.floating]);

  const today = new Date();

  const times = disablePast
    ? ALL_TIME_OPTIONS.filter((t) => {
        const [hours, minutes] = t.split(":").map(Number);
        const selectedTime = new Date(date);
        selectedTime.setHours(hours, minutes, 0, 0);

        if (isSameDay(date, today)) {
          return selectedTime > today;
        }
        return true;
      })
    : ALL_TIME_OPTIONS;

  const changeTime = (value: string) => {
    setTime(value);
    const [hours, minutes] = value.split(":").map(Number);
    const result = setMinutes(setHours(date, hours), minutes);
    setDate(result);
    onChange?.(result);
  };

  // если текущее время выпало из списка доступных при смене даты — подтягиваем ближайшее валидное
  useEffect(() => {
    if (times.length > 0 && !times.includes(time)) {
      changeTime(times[0]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [date]);

  const updateDate = (newDate: Date) => {
    if (!withTime) {
      const result = startOfDay(newDate);
      setDate(result);
      onChange?.(result);
      return;
    }

    const [hours, minutes] = time.split(":").map(Number);
    const result = setMinutes(setHours(newDate, hours), minutes);
    if (result < new Date()) return;

    setDate(result);
    onChange?.(result);
  };

  const setQuickDate = (days: number) => {
    updateDate(addDays(new Date(), days));
  };

  return (
    <div className={styles.wrapper} ref={refs.setReference}>
      <Input
        id="datetime"
        value={format(date, withTime ? "dd.MM.yy HH:mm" : "dd.MM.yy")}
        onChange={() => {}}
        readOnly
        disabled={disabled}
        onClick={() => setOpen((v) => !v)}
        placeholder="Выберите дату"
      />

      {open &&
        createPortal(
          <div
            className={styles.popup}
            ref={refs.setFloating}
            data-portal-popover
            style={{
              ...floatingStyles,
              visibility: isPositioned ? "visible" : "hidden",
            }}
          >
            <div className={styles.header}>
              <span>{format(currentMonth, "LLLL yyyy", { locale: ru })}</span>
              <div className={styles.arrows}>
                <button
                  type="button"
                  onClick={() => setCurrentMonth((m) => subMonths(m, 1))}
                  disabled={currentMonth <= today}
                >
                  <Icon className="rotate-180" name="arrow-right"></Icon>
                </button>

                <button
                  type="button"
                  onClick={() => setCurrentMonth((m) => addMonths(m, 1))}
                >
                  <Icon name="arrow-right"></Icon>
                </button>
              </div>
            </div>

            <div className={styles.quick}>
              <button type="button" onClick={() => setQuickDate(0)}>
                Сегодня
              </button>
              <button type="button" onClick={() => setQuickDate(1)}>
                Завтра
              </button>
              <button type="button" onClick={() => setQuickDate(7)}>
                Через неделю
              </button>
            </div>

            <DayPicker
              mode="single"
              fixedWeeks
              className={styles.calendar}
              selected={date}
              onSelect={(selected) => {
                if (selected) updateDate(selected);
              }}
              disabled={{ before: startOfDay(today) }}
              month={currentMonth}
              onMonthChange={setCurrentMonth}
              locale={ru}
              showOutsideDays
            />

            {withTime && (
              <div className={styles.time}>
                <span>Время</span>
                <select
                  value={time}
                  onChange={(e) => changeTime(e.target.value)}
                >
                  {times.map((item) => (
                    <option key={item} value={item}>
                      {item}
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>,
          document.body,
        )}
    </div>
  );
}
