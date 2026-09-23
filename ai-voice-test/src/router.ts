export function json(data: unknown, init: ResponseInit = {}): Response {
  const headers = new Headers(init.headers);
  headers.set("content-type", "application/json; charset=utf-8");

  return new Response(JSON.stringify(data), {
    ...init,
    headers,
  });
}

export function handlePublicHttp(request: Request): Response | null {
  const url = new URL(request.url);

  if (request.method === "GET" && url.pathname === "/health") {
    return json({
      ok: true,
      service: "ai-voice-test",
      stage: "B",
    });
  }

  if (url.pathname === "/ws") {
    return null;
  }

  return json(
    {
      error: "not_found",
    },
    { status: 404 },
  );
}
