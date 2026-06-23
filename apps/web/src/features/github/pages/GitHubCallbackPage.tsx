/**
 * GitHub OAuth callback page.
 *
 * GitHub redirects the browser here after the user authorises the OAuth app:
 *   /integrations/github/callback?code=...&state=...
 *
 * This page reads `code` and `state` from the URL, calls the API (with the
 * Bearer token already in memory), and then navigates to the GitHub settings
 * page to show the connected status.
 */
import { useEffect, useRef } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { apiClient } from "@/shared/api/client";
import { useAuthStore } from "@/shared/store/authStore";

export function GitHubCallbackPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const accessToken = useAuthStore((s) => s.accessToken);
  const calledRef = useRef(false);

  useEffect(() => {
    if (calledRef.current) return;
    calledRef.current = true;

    const code = searchParams.get("code");
    const state = searchParams.get("state");

    // If there is no session token redirect to login first, then the user can
    // re-start the GitHub flow.
    if (!accessToken) {
      navigate("/login", { replace: true });
      return;
    }

    if (!code || !state) {
      navigate("/settings/github?error=missing_params", { replace: true });
      return;
    }

    apiClient
      .get("/integrations/github/callback", { params: { code, state } })
      .then(() => {
        navigate("/settings/github?connected=1", { replace: true });
      })
      .catch(() => {
        navigate("/settings/github?error=callback_failed", { replace: true });
      });
  }, [searchParams, navigate, accessToken]);

  return (
    <div className="flex min-h-screen items-center justify-center">
      <p className="text-muted-foreground">Łączenie z GitHubem…</p>
    </div>
  );
}
