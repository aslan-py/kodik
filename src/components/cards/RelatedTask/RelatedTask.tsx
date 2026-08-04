type RelatedTaskProps = {
  title: string;
  details: string;
  label?: string;
  description?: string;
  onClick?: () => void;
};

export function RelatedTask({ title, details, label, description, onClick }: RelatedTaskProps) {
  return (
    <div className="space-y-4 text-sm">
      <p className="font-medium">{label ?? "Связанная задача"}</p>
      {description && (
        <p className="text-(--color-secondary) text-xs">{description}</p>
      )}
      <button
        className="surface-block interactive-surface flex flex-col items-start p-4 w-full text-left rounded-lg cursor-pointer"
        onClick={onClick}
      >
        <span className="text-sm font-medium">
          {title}
        </span>
        <span className="text-xs text-(--color-secondary) font-normal mt-auto pt-2">
          {details}
        </span>
      </button>
    </div>
  );
}