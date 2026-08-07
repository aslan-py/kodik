import { useEffect, useState } from "react";

export function useTablePagination<T>(filters: T) {
  const [page, setPage] = useState(1);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setPage(1);
  }, [filters]);

  return {
    page,
    setPage,
  };
}