import { DurableObject } from "cloudflare:workers";
import { handlePublicHttp, json } from "./router";

export interface Env {
  CALL_SESSION: DurableObjectNamespace;
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const publicResponse = handlePublicHttp(request);
    if (publicResponse) {
      return publicResponse;
    }

    const upgrade = request.headers.get("Upgrade");
    if (request.method !== "GET" || upgrade?.toLowerCase() !== "websocket") {
      return json(
        { error: "websocket_upgrade_required" },
        { status: 426 },
      );
    }

    const id = env.CALL_SESSION.newUniqueId();
    const stub = env.CALL_SESSION.get(id);
    return stub.fetch(request);
  },
} satisfies ExportedHandler<Env>;

export class CallSession extends DurableObject<Env> {
  async fetch(request: Request): Promise<Response> {
    const upgrade = request.headers.get("Upgrade");
    if (request.method !== "GET" || upgrade?.toLowerCase() !== "websocket") {
      return json(
        { error: "websocket_upgrade_required" },
        { status: 426 },
      );
    }

    const pair = new WebSocketPair();
    const [client, server] = Object.values(pair);

    this.ctx.acceptWebSocket(server);
    server.serializeAttachment({
      connectedAt: Date.now(),
    });

    return new Response(null, {
      status: 101,
      webSocket: client,
    });
  }

  webSocketMessage(ws: WebSocket, message: string | ArrayBuffer): void {
    ws.send(message);
  }

  webSocketClose(
    _ws: WebSocket,
    _code: number,
    _reason: string,
    _wasClean: boolean,
  ): void {
    // Stage B only: no persistence and no summary yet.
  }
}
