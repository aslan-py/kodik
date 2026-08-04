"use client";

import { useCallback, useEffect, useState } from "react";
import styles from "./table.module.css";

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

  emptyText?: string;
  className?: string;

  pageSize?: number;

  resetPaginationKey?: string;

  //  * Используется для стабильного key строк
  getRowKey?: (item: T, index: number) => string | number;
};

export function Table<T>({
  data,
  columns,
  pageSize = 10,
  emptyText = "Нет данных по вашему запросу",
  className = "",
  getRowKey,
  resetPaginationKey,
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
    },
    [totalPages],
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
                    }`}
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
            {Array.from(
              {
                length: totalPages,
              },
              (_, i) => i + 1,
            ).map((page) => (
              <button
                key={page}
                onClick={() => goToPage(page)}
                className={`${styles.pageButton} ${
                  safeCurrentPage === page ? styles.pageButtonActive : ""
                }`}
              >
                {page}
              </button>
            ))}
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
