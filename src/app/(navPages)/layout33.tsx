import { DataUpdateStatus } from "@/components/features/DataUpdateStatus";
import React from "react";

export default function layoutTitle({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <>
      <DataUpdateStatus className={`pt-8 pl-8`} lastUpdated={"2026-07-28T16:22:00"} />
      <div>{children}</div>
    </>
  );
}
// 