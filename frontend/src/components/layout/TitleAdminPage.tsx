import { dateToDayView } from "@/helpers/date";
import { DataUpdateStatus } from "@/components/features/DataUpdateStatus";

type metricsOption = {
  label: string;
  value: number;
};

type TitleAdminPageProps = {
  title: string;
  text: string;
  metrics?: metricsOption[];
  dataToday?: boolean;
  lastUpdated?: Date | string | null;
};

export default function TitleAdminPage({
  title,
  text,
  metrics,
  dataToday,
  lastUpdated,
}: TitleAdminPageProps) {
  return (
    <div className="mb-8 grid grid-cols-[1fr_auto] items-end gap-x-30">
      {/* Левый блок: заголовок + описание */}
      <div className="flex flex-col gap-2">
        <DataUpdateStatus lastUpdated={lastUpdated ?? null} />
        <h2 className="text-5xl font-semibold">{title}</h2>
        <p className="text-sm text-(--color-secondary)">
          {dataToday && <span>{dateToDayView()} · </span>}
          {text}
        </p>
      </div>

      {/* Правый блок: метрики */}
      {metrics ? (
        <div className="grid auto-cols-auto grid-flow-col gap-6">
          {metrics.map((metric, index) => (
            <div key={index} className="flex flex-col">
              <span
                className={
                  index === 0
                    ? "text-5xl font-semibold text-(--color-ink)"
                    : "text-4xl font-semibold text-(--color-ink)"
                }
              >
                {metric.value}
              </span>
              <span className="whitespace-nowrap text-xs text-(--color-secondary)">
                {metric.label}
              </span>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}
