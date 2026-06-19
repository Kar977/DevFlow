import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";
import { useAuthStore } from "@/shared/store/authStore";

export const authQueryKeys = {
  me: ["auth", "me"] as const,
};

export function useMeQuery() {
  const token = useAuthStore((s) => s.accessToken);
  return useQuery({
    queryKey: authQueryKeys.me,
    queryFn: async () => {
      const res = await apiClient.get("/auth/me");
      return res.data;
    },
    enabled: !!token,
  });
}
