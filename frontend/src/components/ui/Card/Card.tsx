"use client";
import type { ReactNode } from "react";
import { Modal } from "@/components/ui/Modal/Modal";
import { Icon } from "@/components/ui/Icon/Icon";
import styles from "./card.module.css";

export type CardHeaderButton = {
  icon: ReactNode;
  onClick: () => void;
  label: string;
};

export type CardProps = {
  isOpen: boolean;
  onClose: () => void;
  header: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  onCopyLink?: () => void;
  onOpenSource?: () => void;
};

export function Card({
  isOpen,
  onClose,
  header,
  children,
  footer,
  onCopyLink,
  onOpenSource,
}: CardProps) {
  return (
    <Modal isOpen={isOpen} onClose={onClose}>
      <div className={styles.wrapper}>
        <div className={styles.sideButtons}>
          <button
            className={styles.iconButton}
            onClick={onClose}
            title="Закрыть"
          >
            <Icon name="close" />
          </button>

          {onCopyLink && (
            <button
              className={styles.iconButtonInverse}
              onClick={onCopyLink}
              title="Копировать ссылку"
            >
              <Icon name="copylink" />
            </button>
          )}
          {onOpenSource && (
            <button
              className={styles.iconButtonInverse}
              onClick={onOpenSource}
              title="Открыть источник"
            >
              <Icon name="open-source" />
            </button>
          )}
          
        </div>
        <div className={styles.card}>
          <div className={styles.content}>{header}{children}</div>
          {footer && <div className={styles.footer}>{footer}</div>}
        </div>
      </div>
    </Modal>
  );
}