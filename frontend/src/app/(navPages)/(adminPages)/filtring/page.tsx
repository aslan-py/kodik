"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import Loader from "@/app/loading";

function HomeContent() {
  const { user } = useAuth();
  const { logout } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (user && user.role !== "pending") {
      router.replace("/filtring/common");
    }
  }, [user, router]);
  return <Loader />;
}

export default function HomePage() {
  return (
    <>
      <HomeContent />
    </>
  );
}
