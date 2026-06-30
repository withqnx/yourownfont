// Cloudflare Worker entry: routes every request to a single container instance.
//
// The FastAPI app keeps built fonts in process memory (POST /api/build then
// GET /api/font/{id}), so all traffic must reach the SAME container — hence a
// fixed "main" instance rather than getRandom(). Swap to R2/DO storage before
// scaling to multiple instances.
import { Container } from "@cloudflare/containers";

export class FontContainer extends Container {
  defaultPort = 8080;        // matches Dockerfile (uvicorn on 8080)
  sleepAfter = "20m";        // stop after 20m idle; cold start ~2-3s
  enableInternet = false;    // app makes no outbound calls
}

interface Env {
  FONT_CONTAINER: DurableObjectNamespace<FontContainer>;
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const container = env.FONT_CONTAINER.getByName("main");
    await container.startAndWaitForPorts();
    return container.fetch(request);
  },
};
