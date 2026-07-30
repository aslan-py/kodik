import styles from "./deadline.module.css";

export type DeadlineStatus = "planned" | "remaining" | "overdue" | "done";

export type DeadlineStateProps = {
  date: string;
  status: DeadlineStatus;
};

const labelMap: Record<DeadlineStatus, string> = {
  planned:   "По плану",
  remaining: "Осталось 6 часов",
  overdue:   "Просрочено на 2 дня",
  done:      "Выполнено",
};

export function DeadlineState({ date, status }: DeadlineStateProps) {
  return (
    <div className={styles.wrapper}>
      <span className={`${styles.date} ${styles[status]}`}>{date}</span>
      <span className={styles.label}>{labelMap[status]}</span>
    </div>
  );
}

export default DeadlineState;