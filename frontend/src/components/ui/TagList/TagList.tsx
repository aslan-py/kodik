"use client";

import { useState } from "react";
import styles from "./taglist.module.css";

type TagListProps = {
  items: string[];
  /** Начальное состояние: свёрнут (true) или развёрнут (false) */
  defaultExpanded?: boolean;
};

function pluralize(n: number): string {
  if (n % 10 === 1 && n % 100 !== 11) return `${n} связанная публикация`;
  if (n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 10 || n % 100 >= 20)) return `${n} связанных публикации`;
  return `${n} связанных публикаций`;
}

export function TagList({
  items,
  defaultExpanded = false,
}: TagListProps) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const collapsible = items.length > 1;
  const shown = collapsible && !expanded ? items.slice(0, 1) : items;

  const handleClick = () => {
    if (collapsible) setExpanded((prev) => !prev);
  };

  return (
    <ul
      className={styles.list}
      role={collapsible ? "button" : undefined}
      tabIndex={collapsible ? 0 : undefined}
      onClick={handleClick}
      onKeyDown={(e) => {
        if (collapsible && (e.key === "Enter" || e.key === " ")) {
          e.preventDefault();
          setExpanded((prev) => !prev);
        }
      }}
      style={{
        cursor: collapsible ? "pointer" : "default",
        listStyle: "none",
      }}
    >
      {shown.map((item, i) => (
        <li className={styles.badge} key={i}><span>{item}</span></li>
      ))}
      {collapsible && !expanded && (
        <li>
          <span className={styles.badge}>{pluralize(items.length - 1)}</span>
        </li>
      )}
    </ul>
  );
}

export default TagList;