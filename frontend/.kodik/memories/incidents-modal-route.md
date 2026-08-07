---
title: "Модальный маршрут событий"
---

# Модальный маршрут событий (Next.js App Router)

Паттерн «модального маршрута» (аналог `<Routes location>` из React Router) для карточки события реализован через параллельный + перехватывающий маршруты:

- `src/app/(navPages)/incidents/layout.tsx` — рендерит `children` (список) и `modal` (карточку) параллельно.
- `src/app/(navPages)/incidents/@modal/(.)[id]/page.tsx` — перехват: при клиентской навигации на `/incidents/{id}` карточка открывается поверх списка, `onClose` → `router.back()`.
- `src/app/(navPages)/incidents/@modal/default.tsx` — ОБЯЗАТЕЛЕН fallback для параллельного маршрута, иначе Next падает в 404 при заходе на `/incidents`.
- `src/app/(navPages)/incidents/[id]/page.tsx` — обычная страница при прямом заходе/обновлении.

Клик по строке в `incidents/page.tsx` делает `router.push('/incidents/{id}')`.
