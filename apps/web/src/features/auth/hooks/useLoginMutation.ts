import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { apiClient } from "@/shared/api/client";
import { useAuthStore } from "@/shared/store/authStore";

export function useLoginMutation() {
  const navigate = useNavigate();
  const { login } = useAuthStore();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: { email: string; password: string }) => {
      const tokenRes = await apiClient.post("/auth/login", data);
      const tokens = tokenRes.data as { access_token: string };
      const meRes = await apiClient.get("/auth/me", {
        headers: { Authorization: `Bearer ${tokens.access_token}` },
      });
      return { tokens, user: meRes.data };
    },
    onSuccess: ({ tokens, user }) => {
      login(tokens.access_token, user);
      void queryClient.invalidateQueries();
      void navigate("/dashboard", { replace: true });
    },
  });
}
