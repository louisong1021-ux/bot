export interface Env {}

function json(data: unknown, init: ResponseInit = {}): Response {
  const headers = new Headers(init.headers);
  headers.set("content-type", "application/json; charset=utf-8");

  return new Response(JSON.stringify(data), {
    ...init,
    headers,
  });
}

export default {
  async fetch(request: Request): Promise<Response> {
    const url = new URL(request.url);

    if (request.method === "GET" && url.pathname === "/health") {
      return json({
        ok: true,
        service: "ai-voice-test",
        stage: "A",
      });
    }

    return json(
      {
        error: "not_found",
      },
      { status: 404 },
    );
  },
} satisfies ExportedHandler<Env>;
