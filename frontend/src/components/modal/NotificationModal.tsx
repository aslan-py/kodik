"use client";

import { Modal } from "@/components/ui/Modal/Modal";
import { Button } from "@/components/ui/Button";
import { Icon } from "../ui/Icon";

type NotificationModalProps = {
  isOpen: boolean;
  onClose: () => void;
  /** Основной текст сообщения */
  text: string;
  /** Необязательный заголовок над текстом */
  title?: string;
  /** Текст на кнопке. По умолчанию "Ок" */
  buttonText?: string;
  /** Клик по кнопке. Если не передан — просто закрывает модалку через onClose */
  onButtonClick?: () => void;
};

export function NotificationModal({
  isOpen,
  onClose,
  text,
  title,
  buttonText = "Ок",
  onButtonClick,
}: NotificationModalProps) {
  const handleClick = () => {
    if (onButtonClick) {
      onButtonClick();
    } else {
      onClose();
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose}>
      <div className="m-auto max-w-110 rounded-xl bg-white p-8 text-center shadow-lg">
        <span className="flex items-center justify-center justify-self-center w-14 h-14 rounded-full bg-[#F4F5F6] mb-5">
          <Icon className="w-full h-full p-2 stroke-[#73B485]" name="check"></Icon>
        </span>
        {title && (
          <h2 className="mb-5 text-xl font-semibold text-(--color-strong)">
            {title}
          </h2>
        )}

        <p className="text-[13px] text-(--color-secondary)">{text}</p>

        <Button
          className="btn mt-6 h-9 text-sm font-medium"
          fullWidth
          variant="primary"
          onClick={handleClick}
        >
          {buttonText}
        </Button>
      </div>
    </Modal>
  );
}