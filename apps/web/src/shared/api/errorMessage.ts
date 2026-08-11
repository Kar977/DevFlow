import axios from "axios";

/** Envelope shape produced by `core/errors.py:error_payload` on the API. */
interface ApiErrorEnvelope {
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
  };
}

/**
 * Extract a user-facing message from an API error.
 *
 * Prefers the message from the standard `{ error: { message } }` envelope;
 * falls back to a network-vs-generic message when the response doesn't carry
 * one (e.g. the request never reached the server).
 */
export function getErrorMessage(
  error: unknown,
  fallback = "Coś poszło nie tak. Spróbuj ponownie."
): string {
  if (axios.isAxiosError<ApiErrorEnvelope>(error)) {
    const message = error.response?.data?.error?.message;
    if (message) return message;
    if (!error.response) {
      return "Brak połączenia z serwerem. Sprawdź sieć i spróbuj ponownie.";
    }
  }
  return fallback;
}

/** The `details` object from the API error envelope, if present. */
export function getErrorDetails(error: unknown): Record<string, unknown> | undefined {
  if (axios.isAxiosError<ApiErrorEnvelope>(error)) {
    return error.response?.data?.error?.details;
  }
  return undefined;
}

/** True for a 409 Conflict response — used to special-case "resource is
 * already in the state you're trying to put it in" errors (e.g. a work
 * session is already active) that callers want to handle with a specific
 * recovery action instead of a generic error toast. */
export function isConflictError(error: unknown): boolean {
  return axios.isAxiosError(error) && error.response?.status === 409;
}
