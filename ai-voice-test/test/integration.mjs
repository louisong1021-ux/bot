const baseUrl = process.env.TEST_BASE_URL ?? "http://127.0.0.1:8787";

const health = await fetch(`${baseUrl}/health`);
if (!health.ok) {
  throw new Error(`health failed with HTTP ${health.status}`);
}

const healthBody = await health.json();
if (
  healthBody?.ok !== true ||
  healthBody?.service !== "ai-voice-test" ||
  healthBody?.stage !== "B"
) {
  throw new Error(`unexpected health response: ${JSON.stringify(healthBody)}`);
}

const wsUrl = baseUrl.replace(/^http/, "ws") + "/ws";

await new Promise((resolve, reject) => {
  const ws = new WebSocket(wsUrl);
  const timer = setTimeout(() => {
    ws.close();
    reject(new Error("WebSocket integration test timed out"));
  }, 10_000);

  ws.addEventListener("open", () => {
    ws.send("stage-b-ping");
  });

  ws.addEventListener("message", (event) => {
    clearTimeout(timer);

    if (event.data !== "stage-b-ping") {
      ws.close();
      reject(new Error(`unexpected WebSocket payload: ${String(event.data)}`));
      return;
    }

    ws.close(1000, "stage-b-test-complete");
    resolve();
  });

  ws.addEventListener("error", () => {
    clearTimeout(timer);
    reject(new Error("WebSocket connection failed"));
  });
});

console.log("Stage B integration passed: health + Durable Object WebSocket echo.");
