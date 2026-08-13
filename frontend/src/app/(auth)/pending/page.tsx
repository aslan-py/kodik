
import { PendingForm } from "@/components/auth/PendingForm";
import { ProtectedRoute } from "@/components/protected-route/protected-route";
import { Metadata } from "next";
export const metadata: Metadata = {
  title: "Вход",
  description: "Ожидание подтверждения",
};
export default function PendingPage() {

  return (
    <>
    <ProtectedRoute onlyUnAuth={false} requiredRoles={["pending"]}>
      <PendingForm />
    </ProtectedRoute>
    </>
  );
}
