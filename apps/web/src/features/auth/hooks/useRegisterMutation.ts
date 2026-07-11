import { useMutation } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { apiClient } from "@/shared/api/client";
import { useAuthStore } from "@/shared/store/authStore";

export function useRegisterMutation() {
  const navigate = useNavigate();
  const { login } = useAuthStore();

  return useMutation({
    mutationFn: async (data: { email: string; password: string; full_name: string }) => {
      const tokenRes = await apiClient.post("/auth/register", data);
      const tokens = tokenRes.data as { access_token: string };
      const meRes = await apiClient.get("/auth/me", {
        headers: { Authorization: `Bearer ${tokens.access_token}` },
      });
      return { tokens, user: meRes.data };
    },
    onSuccess: ({ tokens, user }) => {
      login(tokens.access_token, user);
      void navigate("/dashboard", { replace: true });
    },
  });
}
