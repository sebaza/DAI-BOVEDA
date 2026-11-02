// Constants shared by the local session client (./session) and the Percepción client.
// Kept apart so the Pages bundle can use them without pulling the Google/dev login client.
export const API_BASE_URL = (process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8012").replace(/\/+$/, "");

export const SESSION_TOKEN_STORAGE_KEY = "boveda-dai-session-token";
export const USER_STORAGE_KEY = "boveda-dai-user";
