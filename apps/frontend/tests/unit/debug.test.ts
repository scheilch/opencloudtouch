/**
 * Tests for debug.ts — frontend debug flag + SSE/WebSocket trace logging.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { octDebug, syncDebugFromBackendLevel, initDebugFromBackend } from "../../src/utils/debug";

describe("debug utilities", () => {
  const mockFetch = vi.fn();
  let debugSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    localStorage.clear();
    globalThis.__OCT_DEBUG__ = false;
    mockFetch.mockClear();
    vi.stubGlobal("fetch", mockFetch);
    debugSpy = vi.spyOn(console, "debug").mockImplementation(() => {});
  });

  afterEach(() => {
    debugSpy.mockRestore();
  });

  describe("octDebug", () => {
    it("does not log when the debug flag is off", () => {
      globalThis.__OCT_DEBUG__ = false;

      octDebug("useNowPlaying", "incoming event", { device_id: "ST10-001" });

      expect(debugSpy).not.toHaveBeenCalled();
    });

    it("logs a tagged message when the debug flag is on", () => {
      globalThis.__OCT_DEBUG__ = true;

      octDebug("useNowPlaying", "incoming event", { device_id: "ST10-001" });

      expect(debugSpy).toHaveBeenCalledWith(
        "[useNowPlaying]",
        "incoming event",
        { device_id: "ST10-001" }
      );
    });
  });

  describe("syncDebugFromBackendLevel", () => {
    it("enables debug when level is DEBUG", () => {
      syncDebugFromBackendLevel("DEBUG");
      expect(globalThis.__OCT_DEBUG__).toBe(true);
    });

    it("disables debug for any non-DEBUG level", () => {
      globalThis.__OCT_DEBUG__ = true;
      syncDebugFromBackendLevel("INFO");
      expect(globalThis.__OCT_DEBUG__).toBe(false);
    });

    it("persists the flag to localStorage via the global setter", () => {
      syncDebugFromBackendLevel("DEBUG");
      expect(localStorage.getItem("oct_debug")).toBe("true");
    });
  });

  describe("initDebugFromBackend", () => {
    it("syncs the debug flag from a successful /api/logs/level response", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ level: "DEBUG" }),
      });

      await initDebugFromBackend();

      expect(mockFetch).toHaveBeenCalledWith("/api/logs/level");
      expect(globalThis.__OCT_DEBUG__).toBe(true);
    });

    it("silently no-ops when the response is not ok", async () => {
      mockFetch.mockResolvedValueOnce({ ok: false });

      await expect(initDebugFromBackend()).resolves.toBeUndefined();
      expect(globalThis.__OCT_DEBUG__).toBe(false);
    });

    it("silently no-ops on a network error", async () => {
      mockFetch.mockRejectedValueOnce(new Error("network down"));

      await expect(initDebugFromBackend()).resolves.toBeUndefined();
      expect(globalThis.__OCT_DEBUG__).toBe(false);
    });
  });

  describe("non-browser environment (SSR)", () => {
    afterEach(() => {
      vi.unstubAllGlobals();
    });

    it("skips the localStorage-backed init when window is undefined at module load", async () => {
      vi.stubGlobal("window", undefined);
      vi.resetModules();

      await expect(import("../../src/utils/debug")).resolves.toBeDefined();
    });

    it("syncDebugFromBackendLevel no-ops when window is undefined", async () => {
      vi.resetModules();
      const mod = await import("../../src/utils/debug");
      globalThis.__OCT_DEBUG__ = false;
      vi.stubGlobal("window", undefined);

      mod.syncDebugFromBackendLevel("DEBUG");

      expect(globalThis.__OCT_DEBUG__).toBe(false);
    });
  });
});
