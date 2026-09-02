import { apiClient } from "./index";
import type { LoadApiRequest } from "@/src/types/dashboard";

type LoadResponse = {
   id: string;
   org_id: string;
   data: LoadApiRequest;
   created_at: string;
   updated_at: string;
};

type CreateLoadResponse = {
   data: LoadResponse;
   message: string;
};

/**
 * Create a new load with negotiation data
 */
export function createLoad(formData: LoadApiRequest) {
   return apiClient.post<CreateLoadResponse>("/api/loads", formData);
}
