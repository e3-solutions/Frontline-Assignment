/**
 * Generic Axios API Client
 *
 * This is the ONLY file where axios should be imported directly.
 * All other code should use the services that wrap this client.
 *
 * Pattern: No try/catch blocks - use .then/.catch chains as per patterns.md
 */

import axios, { type AxiosInstance, type AxiosRequestConfig, type AxiosResponse } from "axios";

type ApiResponse<T = unknown> = {
   data: T;
   status: number;
   ok: boolean;
};

type ApiError = {
   message: string;
   status?: number;
   data?: unknown;
};

type ApiClientConfig = {
   baseURL?: string;
   timeout?: number;
   headers?: Record<string, string>;
};

class ApiClient {
   private instance: AxiosInstance;

   constructor(config: ApiClientConfig = {}) {
      this.instance = axios.create({
         baseURL: config.baseURL || "",
         timeout: config.timeout || 30000,
         headers: {
            "Content-Type": "application/json",
            ...config.headers,
         },
      });

      // Response interceptor to normalize responses
      this.instance.interceptors.response.use(
         (response) => response,
         (error) => {
            // Pass errors through for handling in service layer
            return Promise.reject(error);
         }
      );
   }

   /**
    * Normalize axios response to our ApiResponse format
    */
   private normalizeResponse<T>(response: AxiosResponse<T>): ApiResponse<T> {
      return {
         data: response.data,
         status: response.status,
         ok: response.status >= 200 && response.status < 300,
      };
   }

   /**
    * Normalize axios error to our ApiError format
    */
   private normalizeError(error: unknown): ApiError {
      if (axios.isAxiosError(error)) {
         const data = error.response?.data as unknown;
         const pick = (value: unknown) =>
            typeof value === "string" && value.trim().length > 0 ? value : undefined;
         const payloadMessage =
            pick(data) ??
            (typeof data === "object" && data !== null
               ? (pick((data as Record<string, unknown>).error) ??
                 pick((data as Record<string, unknown>).message))
               : undefined);

         return {
            message: payloadMessage ?? error.message,
            status: error.response?.status,
            data: error.response?.data,
         };
      }
      return {
         message: error instanceof Error ? error.message : "Unknown error",
      };
   }

   /**
    * Generic request method
    */
   private request<T>(config: AxiosRequestConfig): Promise<ApiResponse<T>> {
      return this.instance
         .request<T>(config)
         .then((response) => this.normalizeResponse<T>(response))
         .catch((error) => {
            const apiError = this.normalizeError(error);
            throw apiError;
         });
   }

   /**
    * GET request
    */
   get<T = unknown>(url: string, config?: AxiosRequestConfig): Promise<ApiResponse<T>> {
      return this.request<T>({ ...config, method: "GET", url });
   }

   /**
    * POST request
    */
   post<T = unknown>(
      url: string,
      data?: unknown,
      config?: AxiosRequestConfig
   ): Promise<ApiResponse<T>> {
      return this.request<T>({ ...config, method: "POST", url, data });
   }

   /**
    * PUT request
    */
   put<T = unknown>(
      url: string,
      data?: unknown,
      config?: AxiosRequestConfig
   ): Promise<ApiResponse<T>> {
      return this.request<T>({ ...config, method: "PUT", url, data });
   }

   /**
    * DELETE request
    */
   delete<T = unknown>(url: string, config?: AxiosRequestConfig): Promise<ApiResponse<T>> {
      return this.request<T>({ ...config, method: "DELETE", url });
   }

   /**
    * PATCH request
    */
   patch<T = unknown>(
      url: string,
      data?: unknown,
      config?: AxiosRequestConfig
   ): Promise<ApiResponse<T>> {
      return this.request<T>({ ...config, method: "PATCH", url, data });
   }
}

/**
 * Default API client instance for internal API calls
 */
export const apiClient = new ApiClient();

/**
 * Create a new API client instance with custom configuration
 * Useful for external APIs with different base URLs
 */
export function createApiClient(config: ApiClientConfig): ApiClient {
   return new ApiClient(config);
}
