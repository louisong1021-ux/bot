import { describe, expect, it } from "vitest";
import worker from "../src/index";

describe("stage A health endpoint", () => {
  it("returns a minimal healthy response", async () => {
    const response = await worker.fetch(
      new Request("https://example.test/health", { method: "GET" }),
    );

    expect(response.status).toBe(200);
    expect(response.headers.get("content-type")).toContain("application/json");
    await expect(response.json()).resolves.toEqual({
      ok: true,
      service: "ai-voice-test",
      stage: "A",
    });
  });

  it("returns 404 for unknown routes", async () => {
    const response = await worker.fetch(
      new Request("https://example.test/not-found", { method: "GET" }),
    );

    expect(response.status).toBe(404);
    await expect(response.json()).resolves.toEqual({
      error: "not_found",
    });
  });

  it("does not accept POST /health", async () => {
    const response = await worker.fetch(
      new Request("https://example.test/health", { method: "POST" }),
    );

    expect(response.status).toBe(404);
  });
});
