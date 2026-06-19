import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";

export interface UpdateProfileData {
  full_name?: string;
  avatar_url?: string;
}

export function useProfileMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: UpdateProfileData) =>
      apiClient.patch("/auth/me", data).then((r) => r.data),
    onSuccess: (user) => qc.setQueryData(["me"], user),
  });
}
