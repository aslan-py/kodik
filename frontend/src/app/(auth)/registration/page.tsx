import RegisterForm from "@/components/auth/RegisterForm";
import { Metadata } from "next";
export const metadata: Metadata = {
  title: 'Регистрация',
  description: 'Создание нового аккаунта',
}
export default function RegisterPage() {
  return <RegisterForm />;
}
