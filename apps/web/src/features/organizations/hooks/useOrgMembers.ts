import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";

export interface MemberResponse {
  id: string;
  org_id: string;
  user_id: string;
  role: "owner" | "admin" | "member";
  joined_at: string;
}

interface MemberListResponse {
  items: MemberResponse[];
  total: number;
}

const membersQueryKey = (orgId: string) =>
  ["organizations", orgId, "members"] as const;

export function useOrgMembersQuery(orgId: string | null) {
  return useQuery({
    queryKey: membersQueryKey(orgId ?? ""),
    enabled: !!orgId,
    queryFn: async (): Promise<MemberResponse[]> => {
      const res = await apiClient.get(`/organizations/${orgId}/members`);
      return (res.data as MemberListResponse).items;
    },
  });
}

export function useInviteMember(orgId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { email: string; role: string }) =>
      apiClient
        .post<MemberResponse>(`/organizations/${orgId}/members`, data)
        .then((r) => r.data),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: membersQueryKey(orgId) }),
  });
}

export function useRemoveMember(orgId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (userId: string) =>
      apiClient.delete(`/organizations/${orgId}/members/${userId}`),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: membersQueryKey(orgId) }),
  });
}
