"use client";

import { useCallback, useEffect, useState } from "react";
import styles from "./table.module.css";

type OptionFilter = {
  label: string;
  value: string;
};

// страницы для отображения: первая, последняя и окно вокруг текущей,
// пропуски заменяются на "..."
function getVisiblePages(
  current: number,
  total: number,
): (number | "...")[] {
  if (total <= 7) {
    return Array.from({ length: total }, (_, i) => i + 1);
  }
  const pages = new Set<number>([1, total, current - 1, current, current + 1]);
  const sorted = [...pages]
    .filter((p) => p >= 1 && p <= total)
    .sort((a, b) => a - b);
  const result: (number | "...")[] = [];
  let prev = 0;
  for (const p of sorted) {
    if (p - prev > 1) result.push("...");
    result.push(p);
    prev = p;
  }
  return result;
}

export type TableColumn<T> = {
  key: keyof T | string;
  header: React.ReactNode;
  render?: (item: T) => React.ReactNode;
  className?: string;
  headerClassName?: string;
  width?: string;
  maxWidth?: string;
  filterOptions?: OptionFilter[];
};

export type TableProps<T> = {
  data: T[];
  columns: TableColumn<T>[];

  emptyText?: string;
  className?: string;

  pageSize?: number;

  // * Вызывается при переходе на последнюю страницу (для подгрузки данных)
  onReachLastPage?: () => void;

  resetPaginationKey?: string;

  //  * Используется для стабильного key строк
  getRowKey?: (item: T, index: number) => string | number;
  // * Клик по строке таблицы
  onRowClick?: (item: T) => void;
};

export function Table<T>({
  data,
  columns,
  pageSize = 10,
  emptyText = "Нет данных по вашему запросу",
  className = "",
  getRowKey,
  resetPaginationKey,
  onReachLastPage,
  onRowClick,
}: TableProps<T>) {
  // номер страницы
  const [currentPage, setCurrentPage] = useState(1);
  // количество страниц
  const totalPages = Math.max(1, Math.ceil(data.length / pageSize));
  // защита от перехода на несуществующую страницу
  const safeCurrentPage = Math.min(currentPage, totalPages);

  // начальный индекс
  const startIndex = (safeCurrentPage - 1) * pageSize;
  // отображаемые строки
  const pageData = data.slice(startIndex, startIndex + pageSize);
  // странички
  const startItem = data.length === 0 ? 0 : startIndex + 1;
  const endItem = Math.min(startIndex + pageSize, data.length);

  // переход на первую страницу 
  useEffect(() => {
    if (resetPaginationKey !== undefined) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setCurrentPage(1);
    }
  }, [resetPaginationKey]);

  // переход на страницу
  const goToPage = useCallback(
    (page: number) => {
      if (page < 1 || page > totalPages) return;
      setCurrentPage(page);
      if (page === totalPages) onReachLastPage?.();
    },
    [totalPages, onReachLastPage],
  );

  return (
    <div className={`${styles.wrapper} ${className}`}>
      <div className={styles.tableContainer}>
        <div className={styles.scrollable}>
          <table className={styles.table}>
            <thead className={styles.thead}>
              <tr className={styles.headerRow}>
                {columns.map((column) => (
                  <th
                    key={String(column.key)}
                    className={`${styles.headerCell} ${
                      column.headerClassName ?? ""
                    }`}
                    style={{
                      width: column.width,
                      maxWidth: column.maxWidth,
                    }}
                  >
                    {column.header}
                  </th>
                ))}
              </tr>
            </thead>

            <tbody>
              {pageData.length > 0 ? (
                pageData.map((item, rowIndex) => (
                  <tr
                    key={
                      getRowKey
                        ? getRowKey(item, rowIndex)
                        : `${startIndex + rowIndex}`
                    }
                    className={`${styles.bodyRow} ${
                      rowIndex < pageData.length - 1 ? styles.bodyDivider : ""
                    } ${onRowClick ? styles.bodyRowClickable : ""}`}
                    onClick={onRowClick ? () => onRowClick(item) : undefined}
                  >
                    {columns.map((column) => (
                      <td
                        key={String(column.key)}
                        className={`${styles.bodyCell} ${
                          column.className ?? ""
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
                  <td colSpan={columns.length} className={styles.emptyCell}>
                    {emptyText}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className={styles.pagination}>
        <p className={styles.paginationInfo}>
          Показано <strong>{startItem}</strong>–<strong>{endItem}</strong> из{" "}
          <strong>{data.length}</strong>
        </p>

        <div className={styles.paginationButtons}>
          <button
            onClick={() => goToPage(safeCurrentPage - 1)}
            disabled={safeCurrentPage === 1}
            className={styles.pageButton}
          >
            {"<"}
          </button>

          <div className="flex items-center gap-1">
            {getVisiblePages(safeCurrentPage, totalPages).map((page, i) =>
              page === "..." ? (
                <span key={`ellipsis-${i}`} className={styles.pageEllipsis}>
                  ...
                </span>
              ) : (
                <button
                  key={page}
                  onClick={() => goToPage(page)}
                  className={`${styles.pageButton} ${
                    safeCurrentPage === page ? styles.pageButtonActive : ""
                  }`}
                >
                  {page}
                </button>
              ),
            )}
          </div>

          <button
            onClick={() => goToPage(safeCurrentPage + 1)}
            disabled={safeCurrentPage === totalPages}
            className={styles.pageButton}
          >
            {">"}
          </button>
        </div>
      </div>
    </div>
  );
}
