import { z } from "zod";

export const OrganizationSchema = z.object({
  id: z.string().uuid(),
  name: z.string(),
  slug: z.string(),
  description: z.string().nullable(),
  created_by: z.string().uuid(),
  created_at: z.string().datetime(),
  updated_at: z.string().datetime(),
});

export const OrganizationListResponseSchema = z.object({
  items: z.array(OrganizationSchema),
});

export type Organization = z.infer<typeof OrganizationSchema>;
