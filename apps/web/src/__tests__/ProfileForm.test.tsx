import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ProfileForm } from "@/features/profile/components/ProfileForm";

describe("ProfileForm", () => {
  it("renders with initial name", () => {
    render(<ProfileForm initialName="Jan" onSubmit={vi.fn()} />);
    expect(screen.getByDisplayValue("Jan")).toBeInTheDocument();
  });

  it("calls onSubmit with updated name", async () => {
    const onSubmit = vi.fn();
    render(<ProfileForm initialName="Jan" onSubmit={onSubmit} />);
    const input = screen.getByLabelText(/imię i nazwisko/i);
    await userEvent.clear(input);
    await userEvent.type(input, "Jan Kowalski");
    await userEvent.click(screen.getByRole("button", { name: /zapisz/i }));
    await waitFor(() => expect(onSubmit).toHaveBeenCalledWith({ full_name: "Jan Kowalski", avatar_url: undefined }));
  });

  it("shows validation error when name is too short", async () => {
    render(<ProfileForm initialName="" onSubmit={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: /zapisz/i }));
    await waitFor(() => expect(screen.getByText(/co najmniej 2 znaki/i)).toBeInTheDocument());
  });

  it("shows error for invalid avatar URL", async () => {
    render(<ProfileForm initialName="Jan Kowalski" onSubmit={vi.fn()} />);
    const avatarInput = screen.getByLabelText(/url awatara/i);
    await userEvent.type(avatarInput, "not-a-url");
    await userEvent.click(screen.getByRole("button", { name: /zapisz/i }));
    await waitFor(() => expect(screen.getByText(/nieprawidłowy url/i)).toBeInTheDocument());
  });
});
