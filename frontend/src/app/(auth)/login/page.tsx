import LoginForm from "@/components/auth/LoginForm";
import { Metadata } from "next";

export const metadata: Metadata = {
  title: "Вход",
  description: "Вход в рабочее пространство",
};

export default function LoginPage() {
  return <LoginForm />;
}
