/**
 * Tests for the frontend log buffer utility
 */
import { describe, it, expect } from "vitest";
import { getLogEntries, initLogBuffer } from "../../src/utils/logBuffer";

describe("logBuffer", () => {
  it("captures console.warn output with correct timestamp/level/message shape, and getLogEntries returns a fresh copy each call", () => {
    initLogBuffer();

    // Force an entry to actually exist by producing a log via the patched console.
    const uniqueMessage = `test-log-entry-unique-string-${Date.now()}`;
    console.warn(uniqueMessage);

    const entries = getLogEntries();
    const entry = entries.find((e) => e.message === uniqueMessage);

    // Unconditional — no `if` guard. If the entry isn't there, this test must fail.
    expect(entry).toBeDefined();
    expect(entry).toMatchObject({
      level: "WARN",
      message: uniqueMessage,
    });
    // timestamp must be a valid ISO-8601 string (as produced by new Date().toISOString())
    expect(typeof entry!.timestamp).toBe("string");
    expect(new Date(entry!.timestamp).toISOString()).toBe(entry!.timestamp);

    // getLogEntries returns a copy (not the internal array) — folded in from the
    // now-redundant standalone "returns a copy" test.
    expect(getLogEntries()).not.toBe(getLogEntries());
  });
});
