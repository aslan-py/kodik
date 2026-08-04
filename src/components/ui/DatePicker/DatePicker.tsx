"use client";

import { useState, useRef, useEffect } from "react";

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

type DateTimePickerProps = {
  value?: Date;

  onChange?: (date: Date) => void;
};

export function DateTimePicker({ value, onChange }: DateTimePickerProps) {
  const [open, setOpen] = useState(false);

  const [date, setDate] = useState<Date>(value ?? new Date());

  const [time, setTime] = useState(format(value ?? new Date(), "HH:mm"));
  const [currentMonth, setCurrentMonth] = useState(value ?? new Date());
  const wrapperRef = useRef<HTMLDivElement>(null);

  // закрытие при клике вне компонента

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (
        wrapperRef.current &&
        !wrapperRef.current.contains(e.target as Node)
      ) {
        setOpen(false);
      }
    };

    document.addEventListener("mousedown", handler);

    return () => document.removeEventListener("mousedown", handler);
  }, []);
  const today = new Date();

  const updateDate = (newDate: Date) => {
    const [hours, minutes] = time.split(":").map(Number);

    const result = setMinutes(setHours(newDate, hours), minutes);
    if (result < new Date()) {
      return;
    }
    setDate(result);

    onChange?.(result);
  };

  const setQuickDate = (days: number) => {
    updateDate(addDays(new Date(), days));
  };

  const changeTime = (value: string) => {
    setTime(value);

    const [hours, minutes] = value.split(":").map(Number);

    const result = setMinutes(setHours(date, hours), minutes);

    setDate(result);

    onChange?.(result);
  };
  const generateTimeOptions = (startHour = 7, endHour = 0, step = 60) => {
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

      if (currentHour === 24) {
        currentHour = 0;
      }

      // дошли до 00:00
      if (currentHour === endHour && currentMinute === 0) {
        result.push("00:00");
        break;
      }
    }

    return result;
  };

  const times = generateTimeOptions().filter((time) => {
    const [hours, minutes] = time.split(":").map(Number);

    const selectedTime = new Date(date);

    selectedTime.setHours(hours, minutes, 0, 0);

    // если выбран сегодня
    if (isSameDay(date, today)) {
      return selectedTime > today;
    }

    return true;
  });
  return (
    <div className={styles.wrapper} ref={wrapperRef}>
      <Input
        id="datetime"
        value={format(date, "dd.MM.yy HH:mm")}
        onChange={() => {}}
        readOnly
        onClick={() => setOpen(true)}
        placeholder="Выберите дату"
      />

      {open && (
        <div className={styles.popup}>
          <div className={styles.header}>
            <button
              type="button"
              onClick={() => setCurrentMonth(subMonths(currentMonth, 1))}
              disabled={currentMonth <= today}
            >
              ←
            </button>

            <span>
              {format(currentMonth, "LLLL yyyy", {
                locale: ru,
              })}
            </span>

            <button
              type="button"
              onClick={() => setCurrentMonth(addMonths(currentMonth, 1))}
            >
              →
            </button>
          </div>

          <div className={styles.quick}>
            <button onClick={() => setQuickDate(0)}>Сегодня</button>

            <button onClick={() => setQuickDate(1)}>Завтра</button>

            <button onClick={() => setQuickDate(7)}>Через неделю</button>
          </div>

          <DayPicker
            mode="single"
            fixedWeeks
            className={styles.calendar}
            selected={date}
            // onSelect={(value) => {
            //   if (value) updateDate(value);
            // }}
            onSelect={(selected) => {
              if (selected) {
                updateDate(selected);
              }
            }}
            disabled={{
              before: startOfDay(today),
            }}
            month={currentMonth}
            onMonthChange={setCurrentMonth}
            locale={ru}
            showOutsideDays
          />

          <div className={styles.time}>
            <span>Время</span>

            <select value={time} onChange={(e) => changeTime(e.target.value)}>
              {times.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </div>
        </div>
      )}
    </div>
  );
}
