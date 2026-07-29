"use client";
import { useEffect, useMemo, useState } from "react";
type OptionFilter = {
  label: string;
  value: string;
};
export type TableColumn<T> = {
  key: keyof T | string;
  header: React.ReactNode;
  render?: (item: T) => React.ReactNode;
  className?: string;
  headerClassName?: string;
  width?: string;
  filterOptions?: OptionFilter[];
};

export type TableProps<T> = {
  data: T[];
  columns: TableColumn<T>[];
  pageSize?: number;
  emptyText?: string;
  className?: string;
};

export function Table<T>({
  data,
  columns,
  pageSize = 10,
  emptyText = "Нет данных",
  className = "",
}: TableProps<T>) {
  const [currentPage, setCurrentPage] = useState(1);

  const totalPages = Math.max(1, Math.ceil(data.length / pageSize));

  useEffect(() => {
    if (currentPage > totalPages) {
      setCurrentPage(totalPages);
    }
  }, [currentPage, totalPages]);

  const startIndex = (currentPage - 1) * pageSize;

  const pageData = useMemo(
    () => data.slice(startIndex, startIndex + pageSize),
    [data, startIndex, pageSize]
  );

  const startItem = data.length === 0 ? 0 : startIndex + 1;
  const endItem = Math.min(startIndex + pageSize, data.length);

  const goToPage = (page: number) => {
    if (page < 1 || page > totalPages) return;
    setCurrentPage(page);
  };

  return (
    <div className={`space-y-4 ${className}`}>
      <div className="overflow-hidden ">
        <div className="overflow-x-auto">
          <table className="min-w-full text-left">
            <thead className="rounded-[10]">
              <tr className="bg-(--color-surface) rounded-[10]">
                {columns.map((column) => (
                  <th
                    key={String(column.key)}
                    className={`px-3.5 py-3 text-xs font-medium capitalize tracking-wide text-(--color-secondary) ${column.headerClassName ?? ""
                      }`}
                    style={{ width: column.width }}
                  >
                    {column.header}
                  </th>
                ))}
              </tr>
            </thead>

            <tbody className="divide-y divide-zinc-200">
              {pageData.length > 0 ? (
                pageData.map((item, rowIndex) => (
                  <tr
                    key={rowIndex}
                    className="transition-colors hover:bg-(--color-accent-light)"
                  >
                    {columns.map((column) => (
                      <td
                        key={String(column.key)}
                        className={`px-3.5 py-3 text-sm ${column.className ?? ""
                          }`}
                      >
                        {column.render
                          ? column.render(item)
                          : String(item[column.key as keyof T] ?? "")}
                      </td>
                    ))}
                  </tr>
                ))
              ) : (
                <tr>
                  <td
                    colSpan={columns.length}
                    className="px-6 py-10 text-center text-sm text-zinc-500"
                  >
                    {emptyText}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm text-zinc-500">
          Показано <strong>{startItem}</strong>–<strong>{endItem}</strong> из{" "}
          <strong>{data.length}</strong>
        </p>
              {/* стрелка влево */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => goToPage(currentPage - 1)}
            disabled={currentPage === 1}
            className="rounded-lg px-4 py-2 text-sm disabled:cursor-not-allowed disabled:opacity-50 hover:bg-zinc-200"
          >
            {'<'}
          </button>

          <div className="flex items-center gap-1">
            {Array.from({ length: totalPages }, (_, i) => i + 1).map((page) => (
              <button
                key={page}
                onClick={() => goToPage(page)}
                className={`rounded-lg px-4 py-2 text-sm transition-colors ${currentPage === page
                  ? "bg-(--color-accent-light) text-(--color-accent)"
                  : " hover:bg-zinc-200"
                  }`}
              >
                {page}
              </button>
            ))}
          </div>
            {/* стрелка вправо */}
          <button
            onClick={() => goToPage(currentPage + 1)}
            disabled={currentPage === totalPages}
            className="rounded-lg px-4 py-2 text-sm disabled:cursor-not-allowed disabled:opacity-50 hover:bg-zinc-200"
          >
            {'>'}
          </button>
        </div>
      </div>
    </div>
  );
}