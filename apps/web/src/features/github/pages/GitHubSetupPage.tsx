/**
 * GitHub App setup redirect page.
 *
 * GitHub redirects the browser here after the App is installed or updated:
 *   /integrations/github/setup?installation_id=...&setup_action=...&state=...
 *
 * The page links the installation to the DevFlow organization carried in the
 * signed `state` and then navigates to the GitHub settings page.
 */
import { useEffect, useRef } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { apiClient } from "@/shared/api/client";
import { useAuthStore } from "@/shared/store/authStore";

export function GitHubSetupPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const accessToken = useAuthStore((s) => s.accessToken);
  const calledRef = useRef(false);

  useEffect(() => {
    if (calledRef.current) return;
    calledRef.current = true;

    const installationId = searchParams.get("installation_id");
    const setupAction = searchParams.get("setup_action") ?? "install";
    const state = searchParams.get("state");

    if (!accessToken) {
      navigate("/login", { replace: true });
      return;
    }

    if (!installationId || !state) {
      navigate("/settings/github?error=missing_params", { replace: true });
      return;
    }

    apiClient
      .post("/integrations/github/app/setup", {
        installation_id: Number(installationId),
        setup_action: setupAction,
        state,
      })
      .then(() => {
        navigate("/settings/github?installed=1", { replace: true });
      })
      .catch(() => {
        navigate("/settings/github?error=setup_failed", { replace: true });
      });
  }, [searchParams, navigate, accessToken]);

  return (
    <div className="flex min-h-screen items-center justify-center">
      <p className="text-muted-foreground">Łączenie instalacji GitHub…</p>
    </div>
  );
}
