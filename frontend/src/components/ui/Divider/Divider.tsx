import styles from "./divider.module.css";

export function Divider({ className = "" }: { className?: string }) {
    return (
        <hr
            className={`${styles.divider} ${className}`}
        />
    );
}