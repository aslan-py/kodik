export type TaskCreatePayload = {
  incidentId: string;
  action: string;
  department: string;
  deadline: string;
  expectedResult: string;
  comment?: string;
};
