import styles from "./notification.module.css";

export function Notification() {
  return (
    <div className={styles.notification}>
      <span className={styles.dot} />
      <span>Задача успешно создана, событие передано в работу.</span>
    </div>
  );
}

export default Notification;