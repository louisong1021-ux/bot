import { describe, expect, it } from "vitest";
import { handlePublicHttp } from "../src/router";

describe("public HTTP routing", () => {
  it("returns a minimal healthy response", async () => {
    const response = handlePublicHttp(
      new Request("https://example.test/health", { method: "GET" }),
    );

    expect(response).not.toBeNull();
    expect(response?.status).toBe(200);
    expect(response?.headers.get("content-type")).toContain("application/json");
    await expect(response?.json()).resolves.toEqual({
      ok: true,
      service: "ai-voice-test",
      stage: "B",
    });
  });

  it("returns 404 for unknown routes", async () => {
    const response = handlePublicHttp(
      new Request("https://example.test/not-found", { method: "GET" }),
    );

    expect(response).not.toBeNull();
    expect(response?.status).toBe(404);
    await expect(response?.json()).resolves.toEqual({
      error: "not_found",
    });
  });

  it("does not accept POST /health", () => {
    const response = handlePublicHttp(
      new Request("https://example.test/health", { method: "POST" }),
    );

    expect(response?.status).toBe(404);
  });

  it("delegates /ws to the Worker runtime", () => {
    const response = handlePublicHttp(
      new Request("https://example.test/ws", { method: "GET" }),
    );

    expect(response).toBeNull();
  });
});
