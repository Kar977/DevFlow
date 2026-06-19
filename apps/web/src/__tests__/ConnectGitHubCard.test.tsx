import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ConnectGitHubCard } from "@/features/github/components/ConnectGitHubCard";

describe("ConnectGitHubCard", () => {
  it("shows connect button when not connected", () => {
    render(
      <ConnectGitHubCard
        status={{ connected: false }}
        onConnect={vi.fn()}
        onDisconnect={vi.fn()}
        isConnecting={false}
        isDisconnecting={false}
      />
    );
    expect(screen.getByRole("button", { name: /połącz github/i })).toBeInTheDocument();
  });

  it("shows github login and disconnect button when connected", () => {
    render(
      <ConnectGitHubCard
        status={{ connected: true, github_login: "octocat", github_avatar_url: null }}
        onConnect={vi.fn()}
        onDisconnect={vi.fn()}
        isConnecting={false}
        isDisconnecting={false}
      />
    );
    expect(screen.getByText("octocat")).toBeInTheDocument();
    expect(screen.getByText("Połączono")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /rozłącz/i })).toBeInTheDocument();
  });

  it("calls onConnect when connect button clicked", async () => {
    const onConnect = vi.fn();
    render(
      <ConnectGitHubCard
        status={{ connected: false }}
        onConnect={onConnect}
        onDisconnect={vi.fn()}
        isConnecting={false}
        isDisconnecting={false}
      />
    );
    await userEvent.click(screen.getByRole("button", { name: /połącz github/i }));
    expect(onConnect).toHaveBeenCalledOnce();
  });

  it("calls onDisconnect when disconnect button clicked", async () => {
    const onDisconnect = vi.fn();
    render(
      <ConnectGitHubCard
        status={{ connected: true, github_login: "octocat", github_avatar_url: null }}
        onConnect={vi.fn()}
        onDisconnect={onDisconnect}
        isConnecting={false}
        isDisconnecting={false}
      />
    );
    await userEvent.click(screen.getByRole("button", { name: /rozłącz/i }));
    expect(onDisconnect).toHaveBeenCalledOnce();
  });
});
