# Developed by Johnny and JohnnyTech
# Licensed under GNU AGPL 3.0 licence.

import asyncio
import sys
import httpx
import websockets
import json
import time

DEFAULT_SERVER = "wss://tnl.is-a.dev"


def build_url(server: str, subdomain: str):
    return f"{server}/websockets/{subdomain}"


async def run_tunnel(subdomain: str, port: int, server: str):
    uri = build_url(server, subdomain)

    print("JohnnyTunnels")
    print(f"Tunnel target: {server}")
    print(f"Public URL: https://{subdomain}.{server.replace('wss://', '').replace('ws://', '')}")
    print(f"Forwarding → localhost:{port}")
    print(f"If you want to use a CNAME record to forward to the tunnel, the ONLY SUITABLE METHOD is: [CNAME]https://{subdomain}.[YOURDOMAIN.com] points to https://{subdomain}.{server.replace('wss://', '').replace('ws://', '')}")
    print("Ctrl+C to stop\n")

    async with httpx.AsyncClient(follow_redirects=False, timeout=None) as http:

        while True:
            try:
                async with websockets.connect(uri, ping_interval=20, ping_timeout=20) as ws:
                    print("[✓] Connected to tunnel server")

                    while True:
                        message = await ws.recv()
                        data = json.loads(message)

                        request_id = data["request_id"]
                        method = data["method"]
                        path = data["path"]
                        body = data.get("body", "")
                        headers = data.get("headers", {})

                        # Fix host header safely
                        headers["host"] = f"localhost:{port}"

                        try:
                            url = f"http://localhost:{port}/{path.lstrip('/')}" if path else f"http://localhost:{port}/"

                            response = await http.request(
                                method=method,
                                url=url,
                                headers=headers,
                                content=body.encode() if isinstance(body, str) else body,
                            )

                            response_headers = dict(response.headers)

                            # remove unsafe headers
                            response_headers.pop("content-length", None)
                            response_headers.pop("transfer-encoding", None)

                            # fix redirects
                            if "location" in response_headers:
                                loc = response_headers["location"]
                                if loc.startswith("/"):
                                    response_headers["location"] = f"/access_int/{subdomain}{loc}"

                            content_type = response_headers.get("content-type", "")

                            # SAFE BODY HANDLING
                            if "text" in content_type or "json" in content_type:
                                body_out = response.text

                                # HTML rewriting only for text/html
                                if "text/html" in content_type:
                                    body_out = body_out.replace('href="/', f'href="/access_int/{subdomain}/')
                                    body_out = body_out.replace('src="/', f'src="/access_int/{subdomain}/')
                                    body_out = body_out.replace("href='/", f"href='/access_int/{subdomain}/")
                                    body_out = body_out.replace("src='/", f"src='/access_int/{subdomain}/")

                            else:
                                # binary-safe fallback
                                body_out = response.content.decode("utf-8", errors="replace")

                            await ws.send(json.dumps({
                                "request_id": request_id,
                                "status": response.status_code,
                                "headers": response_headers,
                                "body": body_out
                            }))

                        except Exception as e:
                            await ws.send(json.dumps({
                                "request_id": request_id,
                                "status": 502,
                                "headers": {},
                                "body": f"Local server error: {repr(e)}"
                            }))

            except Exception as e:
                print(f"[!] Connection lost: {repr(e)}")
                print("[~] Reconnecting in 3 seconds...")
                await asyncio.sleep(3)


def main():
    if len(sys.argv) not in (3, 4):
        print("Usage: tnl <subdomain> <port> [server]")
        print("Example: tnl momboard 5000 wss://tnl.is-a.dev")
        sys.exit(1)

    subdomain = sys.argv[1]
    port = int(sys.argv[2])
    server = sys.argv[3] if len(sys.argv) == 4 else DEFAULT_SERVER

    try:
        asyncio.run(run_tunnel(subdomain, port, server))
    except KeyboardInterrupt:
        print("\n[!] Tunnel stopped")


if __name__ == "__main__":
    main()
