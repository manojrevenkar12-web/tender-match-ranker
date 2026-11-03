import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../shared/api/client";
import type { LotDetail, LotSummary, Shortlist } from "../../shared/api/types";

export const useLots = (q: string) =>
  useQuery({
    queryKey: ["lots", q],
    queryFn: () => api.get<LotSummary[]>(`/v1/lots?limit=80&q=${encodeURIComponent(q)}`),
  });

export const useLot = (id: number | null) =>
  useQuery({
    queryKey: ["lot", id],
    queryFn: () => api.get<LotDetail>(`/v1/lots/${id}`),
    enabled: id !== null,
  });

export const useShortlist = (id: number | null) =>
  useQuery({
    queryKey: ["shortlist", id],
    queryFn: () => api.get<Shortlist>(`/v1/lots/${id}/shortlist`),
    enabled: id !== null,
  });

export function useInvite(id: number | null) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (firmIds: number[]) =>
      api.post<{ invited: number }>(`/v1/lots/${id}/invitations`, { firm_ids: firmIds, invited_by: "buyer" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["shortlist"] }),
  });
}
