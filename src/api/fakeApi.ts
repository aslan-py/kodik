import { createApi, fakeBaseQuery } from "@reduxjs/toolkit/query/react";
import type { IncidentItem } from "@/types/types";
import type { TaskCreatePayload } from "@/types/task";
import { mockIncidents } from "@/data/mockIncidents";

/* ------------------------------------------------------------------ */
/*  Типы ответов                                                       */
/* ------------------------------------------------------------------ */

export type HistoryItem = {
  text: string;
  createdAt: string;
};

export type TaskItem = {
  id: string;
  incidentId: string;
  action: string;
  department: string;
  deadline: string;
  expectedResult: string;
  comment?: string;
  status: "new" | "in_progress" | "done";
  createdAt: string;
  assigneeName: string;
  assigneeRole: string;
  priority: string;
  object: string;
  category: string;
  type: string;
  source: string;
  incidentTitle: string;
  incidentDescription: string;
  incidentDate: string;
  incidentPriority: string;
  incidentSource: string;
  history: HistoryItem[];
};

export type SourceItem = {
  name: string;
  date: string;
  label: string;
};

export type CommentItem = {
  id: string;
  text: string;
  createdAt: string;
};

/* ------------------------------------------------------------------ */
/*  Мок-хранилище (имитация БД)                                        */
/* ------------------------------------------------------------------ */

let tasksDb: TaskItem[] = [
  {
    id: "task-1",
    incidentId: "Wildberries запускает экспресс-доставку для региональных продавцов",
    action: "Оценить влияние запуска экспресс-доставки Wildberries на региональных продавцов и подготовить возможные варианты реакции.",
    department: "Коммерческий отдел",
    deadline: "07-28-2026 18:00",
    expectedResult: "Краткая оценка риска, список возможных ответных действий и рекомендация по коммуникации для региональных продавцов.",
    status: "in_progress",
    createdAt: "2026-07-26T10:47:00Z",
    assigneeName: "Анна Смирнова",
    assigneeRole: "Коммерческий аналитик",
    priority: "П1",
    object: "Wildberries",
    category: "Маркетплейсы",
    type: "Доставка",
    source: "Коммерсантъ",
    incidentTitle: "Wildberries запускает экспресс-доставку для региональных продавцов",
    incidentDescription: "Запуск сервиса может изменить ожидания продавцов по скорости доставки и повлиять на конкурентные предложения.",
    incidentDate: "26 июля 2026",
    incidentPriority: "П1",
    incidentSource: "Коммерсантъ",
    history: [
      { text: "Задача создана из события.", createdAt: "2026-07-26T10:47:00Z" },
      { text: "Ответственной назначена Анна Смирнова.", createdAt: "2026-07-26T10:48:00Z" },
      { text: "Срок установлен на сегодня, 18:00.", createdAt: "2026-07-26T11:06:00Z" },
    ],
  },
  {
    id: "task-2",
    incidentId: "Ozon расширяет сеть пунктов выдачи в регионах",
    action: "Сравнить покрытие ПВЗ с конкурентами в регионах.",
    department: "Финансовый отдел",
    deadline: "07-29-2026 12:00",
    expectedResult: "Отчёт по регионам",
    status: "done",
    createdAt: "2026-07-26T09:30:00Z",
    assigneeName: "Иван Петров",
    assigneeRole: "Финансовый аналитик",
    priority: "П2",
    object: "Ozon",
    category: "Маркетплейсы",
    type: "Логистика",
    source: "РБК",
    incidentTitle: "Ozon расширяет сеть пунктов выдачи в регионах",
    incidentDescription: "Ozon активно расширяет сеть ПВЗ в регионах, что может повлиять на логистическую привлекательность платформы.",
    incidentDate: "26 июля 2026",
    incidentPriority: "П2",
    incidentSource: "РБК",
    history: [
      { text: "Задача создана из события.", createdAt: "2026-07-26T09:30:00Z" },
      { text: "Ответственным назначен Иван Петров.", createdAt: "2026-07-26T09:35:00Z" },
      { text: "Задача выполнена.", createdAt: "2026-07-29T11:00:00Z" },
    ],
  },
  {
    id: "task-3",
    incidentId: "Wildberries снижает комиссию для новых продавцов",
    action: "Проанализировать влияние снижения комиссии на доходы.",
    department: "Финансовый отдел",
    deadline: "07-28-2026 14:00",
    expectedResult: "Финансовая модель",
    status: "in_progress",
    createdAt: "2026-07-25T11:00:00Z",
    assigneeName: "Ольга Кузнецова",
    assigneeRole: "Финансовый аналитик",
    priority: "П2",
    object: "Wildberries",
    category: "Маркетплейсы",
    type: "Комиссии",
    source: "Коммерсантъ",
    incidentTitle: "Wildberries снижает комиссию для новых продавцов",
    incidentDescription: "Wildberries объявил о снижении комиссии для новых продавцов, что может повлиять на приток селлеров.",
    incidentDate: "25 июля 2026",
    incidentPriority: "П2",
    incidentSource: "Коммерсантъ",
    history: [
      { text: "Задача создана из события.", createdAt: "2026-07-25T11:00:00Z" },
      { text: "Ответственной назначена Ольга Кузнецова.", createdAt: "2026-07-25T11:05:00Z" },
    ],
  },
  {
    id: "task-8",
    incidentId: "Яндекс Маркет ужесточает правила для сторонних продавцов",
    action: "Подготовить ответные меры на ужесточение правил.",
    department: "Коммерческий отдел",
    deadline: "07-30-2026 10:00",
    expectedResult: "План действий",
    status: "in_progress",
    createdAt: "2026-07-20T15:00:00Z",
    assigneeName: "Анна Смирнова",
    assigneeRole: "Коммерческий аналитик",
    priority: "П1",
    object: "Яндекс Маркет",
    category: "Маркетплейсы",
    type: "Правила",
    source: "РБК",
    incidentTitle: "Яндекс Маркет ужесточает правила для сторонних продавцов",
    incidentDescription: "Яндекс Маркет вводит новые требования к продавцам, что может снизить их активность на платформе.",
    incidentDate: "20 июля 2026",
    incidentPriority: "П1",
    incidentSource: "РБК",
    history: [
      { text: "Задача создана из события.", createdAt: "2026-07-20T15:00:00Z" },
      { text: "Ответственной назначена Анна Смирнова.", createdAt: "2026-07-20T15:10:00Z" },
    ],
  },
  {
    id: "task-13",
    incidentId: "Яндекс Маркет инвестирует в автоматизацию складов",
    action: "Оценить влияние автоматизации складов на операционные затраты.",
    department: "Финансовый отдел",
    deadline: "07-31-2026 18:00",
    expectedResult: "Аналитический отчёт",
    status: "in_progress",
    createdAt: "2026-07-15T08:00:00Z",
    assigneeName: "Иван Петров",
    assigneeRole: "Финансовый аналитик",
    priority: "П3",
    object: "Яндекс Маркет",
    category: "Маркетплейсы",
    type: "Инвестиции",
    source: "Коммерсантъ",
    incidentTitle: "Яндекс Маркет инвестирует в автоматизацию складов",
    incidentDescription: "Яндекс Маркет вкладывает средства в автоматизацию складских операций для снижения издержек.",
    incidentDate: "15 июля 2026",
    incidentPriority: "П3",
    incidentSource: "Коммерсантъ",
    history: [
      { text: "Задача создана из события.", createdAt: "2026-07-15T08:00:00Z" },
      { text: "Ответственным назначен Иван Петров.", createdAt: "2026-07-15T08:15:00Z" },
    ],
  },
];

const sourcesDb: SourceItem[] = [
  { name: "Коммерсантъ", date: "26 июл 2026", label: "первоисточник" },
  { name: "РБК", date: "26 июл 2026", label: "первоисточник" },
];

const commentsDb: CommentItem[] = [
  { id: "c1", text: "10:42 · Событие создано из публикации РБК", createdAt: "2026-07-27T10:42:00Z" },
  { id: "c2", text: "10:42 · Событие создано из публикации РБК", createdAt: "2026-07-27T10:42:00Z" },
];

/* ------------------------------------------------------------------ */
/*  Вспомогательная задержка (имитация сети)                           */
/* ------------------------------------------------------------------ */

const delay = (ms: number) => new Promise((r) => setTimeout(r, ms));

/* ------------------------------------------------------------------ */
/*  API-слайс                                                          */
/* ------------------------------------------------------------------ */

export const fakeApi = createApi({
  reducerPath: "fakeApi",
  baseQuery: fakeBaseQuery(),
  tagTypes: ["Incidents", "Tasks", "Sources", "Comments"],
  endpoints: (builder) => ({
    // ─── Инциденты ────────────────────────────────────────────────

    getIncidents: builder.query<IncidentItem[], void>({
      async queryFn() {
        await delay(400);
        return { data: [...mockIncidents] };
      },
      providesTags: ["Incidents"],
    }),

    getIncidentById: builder.query<IncidentItem | undefined, string>({
      async queryFn(incidentTitle) {
        await delay(200);
        const item = mockIncidents.find((i) => i.incident === incidentTitle);
        return { data: item };
      },
      providesTags: (_result, _err, id) => [{ type: "Incidents", id }],
    }),

    // ─── Задачи ───────────────────────────────────────────────────

    getTasks: builder.query<TaskItem[], void>({
      async queryFn() {
        await delay(300);
        return { data: [...tasksDb] };
      },
      providesTags: ["Tasks"],
    }),

    getTaskById: builder.query<TaskItem | undefined, string>({
      async queryFn(taskId) {
        await delay(200);
        const task = tasksDb.find((t) => t.id === taskId);
        return { data: task };
      },
      providesTags: (_result, _err, id) => [{ type: "Tasks", id }],
    }),

    createTask: builder.mutation<TaskItem, TaskCreatePayload>({
      async queryFn(payload) {
        await delay(600);
        const newTask: TaskItem = {
          id: `task-${Date.now()}`,
          incidentId: payload.incidentId,
          action: payload.action,
          department: payload.department,
          deadline: payload.deadline,
          expectedResult: payload.expectedResult,
          comment: payload.comment,
          status: "in_progress",
          createdAt: new Date().toISOString(),
          assigneeName: "",
          assigneeRole: "",
          priority: "",
          object: "",
          category: "",
          type: "",
          source: "",
          incidentTitle: "",
          incidentDescription: "",
          incidentDate: "",
          incidentPriority: "",
          incidentSource: "",
          history: [],
        };
        tasksDb = [newTask, ...tasksDb];
        return { data: newTask };
      },
      invalidatesTags: ["Tasks"],
    }),

    updateTaskStatus: builder.mutation<TaskItem, { taskId: string; status: "new" | "in_progress" | "done" }>({
      async queryFn({ taskId, status }) {
        await delay(300);
        const idx = tasksDb.findIndex((t) => t.id === taskId);
        if (idx === -1) return { error: { status: 404, data: "Task not found" } };
        tasksDb[idx] = { ...tasksDb[idx], status };
        return { data: tasksDb[idx] };
      },
      invalidatesTags: (_result, _err, { taskId }) => [
        "Tasks",
        { type: "Tasks", id: taskId },
      ],
    }),

    // ─── Источники ────────────────────────────────────────────────

    getSources: builder.query<SourceItem[], void>({
      async queryFn() {
        await delay(200);
        return { data: [...sourcesDb] };
      },
      providesTags: ["Sources"],
    }),

    // ─── Комментарии ──────────────────────────────────────────────

    getComments: builder.query<CommentItem[], void>({
      async queryFn() {
        await delay(200);
        return { data: [...commentsDb] };
      },
      providesTags: ["Comments"],
    }),

    addComment: builder.mutation<CommentItem, string>({
      async queryFn(text) {
        await delay(300);
        const newComment: CommentItem = {
          id: `c${Date.now()}`,
          text,
          createdAt: new Date().toISOString(),
        };
        commentsDb.push(newComment);
        return { data: newComment };
      },
      invalidatesTags: ["Comments"],
    }),
  }),
});

/* ------------------------------------------------------------------ */
/*  Хуки (авто-генерация)                                              */
/* ------------------------------------------------------------------ */

export const {
  useGetIncidentsQuery,
  useGetIncidentByIdQuery,
  useGetTasksQuery,
  useGetTaskByIdQuery,
  useCreateTaskMutation,
  useUpdateTaskStatusMutation,
  useGetSourcesQuery,
  useGetCommentsQuery,
  useAddCommentMutation,
} = fakeApi;