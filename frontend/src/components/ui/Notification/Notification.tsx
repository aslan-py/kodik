import styles from "./notification.module.css";

type NotificationProps = {
  type: "success" | "error";
  children?: React.ReactNode;
};

export function Notification({ type, children }: NotificationProps) {
  const dotClass = type === "error" ? styles.dotError : styles.dot;

  return (
    <div className={styles.notification}>
      <span className={dotClass} />
      <span>{children}</span>
    </div>
  );
}