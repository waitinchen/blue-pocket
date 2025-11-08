const DEFAULT_SERVICE_KEY = "RIUvXLm99TG_jOyN6gP1vTYE1fdmXyMxL5tLDzMwFiA";

export const SERVICE_API_KEY =
  (import.meta.env.VITE_SERVICE_API_KEY as string | undefined)?.trim() || DEFAULT_SERVICE_KEY;

export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.trim() || "";

export const CHATKIT_SESSION_ENDPOINT =
  (import.meta.env.VITE_CHATKIT_SESSION_ENDPOINT as string | undefined)?.trim() || "/api/chatkit/session";

