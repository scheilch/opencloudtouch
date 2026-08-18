/**
 * Tests for VolumeSlider.tsx
 *
 * User Story: "Als User möchte ich die Lautstärke präzise steuern"
 *
 * Focus: Functional tests for volume control
 * - Volume display via aria-valuenow
 * - Mute/Unmute toggle
 * - Keyboard navigation (Arrow keys)
 * - Muted visual state
 * - Accessibility (aria-labels)
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import VolumeSlider from "../../src/components/VolumeSlider";

describe("VolumeSlider Component", () => {
  describe("Volume Display & Controls", () => {
    it("should render slider with correct volume and aria range attributes", () => {
      render(
        <VolumeSlider volume={45} onVolumeChange={vi.fn()} muted={false} onMuteToggle={vi.fn()} />
      );
      const slider = screen.getByRole("slider");
      expect(slider).toHaveAttribute("aria-valuemin", "0");
      expect(slider).toHaveAttribute("aria-valuemax", "100");
      expect(slider).toHaveAttribute("aria-valuenow", "45");
    });

    it("should call onVolumeChange with +5 on ArrowRight", () => {
      const mockOnVolumeChange = vi.fn();
      render(
        <VolumeSlider volume={50} onVolumeChange={mockOnVolumeChange} muted={false} onMuteToggle={vi.fn()} />
      );
      fireEvent.keyDown(screen.getByRole("slider"), { key: "ArrowRight" });
      expect(mockOnVolumeChange).toHaveBeenCalledWith(55);
    });

    it("should call onVolumeChange with -5 on ArrowLeft", () => {
      const mockOnVolumeChange = vi.fn();
      render(
        <VolumeSlider volume={50} onVolumeChange={mockOnVolumeChange} muted={false} onMuteToggle={vi.fn()} />
      );
      fireEvent.keyDown(screen.getByRole("slider"), { key: "ArrowLeft" });
      expect(mockOnVolumeChange).toHaveBeenCalledWith(45);
    });

    it("should clamp ArrowLeft at 0", () => {
      const mockOnVolumeChange = vi.fn();
      render(
        <VolumeSlider volume={3} onVolumeChange={mockOnVolumeChange} muted={false} onMuteToggle={vi.fn()} />
      );
      fireEvent.keyDown(screen.getByRole("slider"), { key: "ArrowLeft" });
      expect(mockOnVolumeChange).toHaveBeenCalledWith(0);
    });

    it("should clamp ArrowRight at 100", () => {
      const mockOnVolumeChange = vi.fn();
      render(
        <VolumeSlider volume={98} onVolumeChange={mockOnVolumeChange} muted={false} onMuteToggle={vi.fn()} />
      );
      fireEvent.keyDown(screen.getByRole("slider"), { key: "ArrowRight" });
      expect(mockOnVolumeChange).toHaveBeenCalledWith(100);
    });
  });

  describe("Mute Functionality", () => {
    it("should toggle mute when button clicked", () => {
      const mockOnMuteToggle = vi.fn();
      render(
        <VolumeSlider volume={50} onVolumeChange={vi.fn()} muted={false} onMuteToggle={mockOnMuteToggle} />
      );
      fireEvent.click(screen.getByRole("button", { name: "Mute" }));
      expect(mockOnMuteToggle).toHaveBeenCalledTimes(1);
    });

    it("should apply muted CSS class to track when muted", () => {
      render(
        <VolumeSlider volume={50} onVolumeChange={vi.fn()} muted={true} onMuteToggle={vi.fn()} />
      );
      expect(screen.getByRole("slider")).toHaveClass("muted");
    });

    it("should show unmute label when muted", () => {
      render(
        <VolumeSlider volume={50} onVolumeChange={vi.fn()} muted={true} onMuteToggle={vi.fn()} />
      );
      expect(screen.getByRole("button", { name: "Unmute" })).toBeInTheDocument();
    });

    it("should show mute label when not muted", () => {
      render(
        <VolumeSlider volume={50} onVolumeChange={vi.fn()} muted={false} onMuteToggle={vi.fn()} />
      );
      expect(screen.getByRole("button", { name: "Mute" })).toBeInTheDocument();
    });

    it("should apply muted CSS class to mute button when muted", () => {
      render(
        <VolumeSlider volume={50} onVolumeChange={vi.fn()} muted={true} onMuteToggle={vi.fn()} />
      );
      expect(screen.getByRole("button", { name: "Unmute" })).toHaveClass("muted");
    });
  });

  describe("Accessibility", () => {
    it("should have aria-label Volume on slider", () => {
      render(
        <VolumeSlider volume={50} onVolumeChange={vi.fn()} muted={false} onMuteToggle={vi.fn()} />
      );
      expect(screen.getByRole("slider", { name: "Volume" })).toBeInTheDocument();
    });

    it("should have tabIndex 0 for keyboard access", () => {
      render(
        <VolumeSlider volume={50} onVolumeChange={vi.fn()} muted={false} onMuteToggle={vi.fn()} />
      );
      expect(screen.getByRole("slider")).toHaveAttribute("tabindex", "0");
    });
  });

  describe("Pointer Drag Interactions", () => {
    // jsdom does not implement setPointerCapture / releasePointerCapture
    beforeEach(() => {
      HTMLElement.prototype.setPointerCapture = vi.fn();
      HTMLElement.prototype.releasePointerCapture = vi.fn();
    });
    it("should call onVolumeChange after pointerdown + pointerup", () => {
      const mockOnVolumeChange = vi.fn();
      const { container } = render(
        <VolumeSlider volume={50} onVolumeChange={mockOnVolumeChange} muted={false} onMuteToggle={vi.fn()} />,
      );
      const track = container.querySelector(".volume-track") as HTMLElement;
      // Mock getBoundingClientRect for value calculation
      vi.spyOn(track, "getBoundingClientRect").mockReturnValue({
        left: 0, right: 200, width: 200, top: 0, bottom: 20, height: 20, x: 0, y: 0, toJSON: vi.fn(),
      });

      // Simulate drag: pointerdown at 50% → pointerup at same position
      fireEvent.pointerDown(track, { clientX: 100, pointerId: 1 });
      fireEvent.pointerUp(track, { clientX: 100, pointerId: 1 });

      expect(mockOnVolumeChange).toHaveBeenCalledWith(50);
    });

    it("should update final value based on pointerup position", () => {
      const mockOnVolumeChange = vi.fn();
      const { container } = render(
        <VolumeSlider volume={0} onVolumeChange={mockOnVolumeChange} muted={false} onMuteToggle={vi.fn()} />,
      );
      const track = container.querySelector(".volume-track") as HTMLElement;
      vi.spyOn(track, "getBoundingClientRect").mockReturnValue({
        left: 0, right: 200, width: 200, top: 0, bottom: 20, height: 20, x: 0, y: 0, toJSON: vi.fn(),
      });

      fireEvent.pointerDown(track, { clientX: 10, pointerId: 1 });
      fireEvent.pointerMove(track, { clientX: 150, pointerId: 1 });
      fireEvent.pointerUp(track, { clientX: 150, pointerId: 1 });

      expect(mockOnVolumeChange).toHaveBeenCalledWith(75);
    });

    it("should not call onVolumeChange on pointerMove without pointerDown", () => {
      const mockOnVolumeChange = vi.fn();
      const { container } = render(
        <VolumeSlider volume={50} onVolumeChange={mockOnVolumeChange} muted={false} onMuteToggle={vi.fn()} />,
      );
      const track = container.querySelector(".volume-track") as HTMLElement;

      fireEvent.pointerMove(track, { clientX: 100, pointerId: 1 });

      expect(mockOnVolumeChange).not.toHaveBeenCalled();
    });

    it("should ignore pointerUp without prior pointerDown", () => {
      const mockOnVolumeChange = vi.fn();
      const { container } = render(
        <VolumeSlider volume={50} onVolumeChange={mockOnVolumeChange} muted={false} onMuteToggle={vi.fn()} />,
      );
      const track = container.querySelector(".volume-track") as HTMLElement;

      fireEvent.pointerUp(track, { clientX: 100, pointerId: 1 });

      expect(mockOnVolumeChange).not.toHaveBeenCalled();
    });

    it("should clamp drag value to 0-100 range", () => {
      const mockOnVolumeChange = vi.fn();
      const { container } = render(
        <VolumeSlider volume={50} onVolumeChange={mockOnVolumeChange} muted={false} onMuteToggle={vi.fn()} />,
      );
      const track = container.querySelector(".volume-track") as HTMLElement;
      vi.spyOn(track, "getBoundingClientRect").mockReturnValue({
        left: 100, right: 300, width: 200, top: 0, bottom: 20, height: 20, x: 100, y: 0, toJSON: vi.fn(),
      });

      // Drag past right edge
      fireEvent.pointerDown(track, { clientX: 400, pointerId: 1 });
      fireEvent.pointerUp(track, { clientX: 400, pointerId: 1 });

      expect(mockOnVolumeChange).toHaveBeenCalledWith(100);
    });

    it("should clamp drag to 0 when dragging past left edge", () => {
      const mockOnVolumeChange = vi.fn();
      const { container } = render(
        <VolumeSlider volume={50} onVolumeChange={mockOnVolumeChange} muted={false} onMuteToggle={vi.fn()} />,
      );
      const track = container.querySelector(".volume-track") as HTMLElement;
      vi.spyOn(track, "getBoundingClientRect").mockReturnValue({
        left: 100, right: 300, width: 200, top: 0, bottom: 20, height: 20, x: 100, y: 0, toJSON: vi.fn(),
      });

      // Drag past left edge
      fireEvent.pointerDown(track, { clientX: 50, pointerId: 1 });
      fireEvent.pointerUp(track, { clientX: 50, pointerId: 1 });

      expect(mockOnVolumeChange).toHaveBeenCalledWith(0);
    });
  });
});
