# Developed by Johnny and JohnnyTech
# Licensed under GNU AGPL 3.0 licence.
import asyncio
import sys
import httpx
import websockets
import json

SERVER = "ws://localhost:8080"

async def run_tunnel(subdomain: str, port: int):
    uri = f"{SERVER}/websockets/{subdomain}"
    print(f"JohnnyTunnels")
    print(f"Connecting to {subdomain}.{SERVER.replace('ws://', '')}...")

    async with websockets.connect(uri) as ws:
        print(f"Tunnel live at https://{subdomain}.{SERVER.replace('ws://', '')}")
        print(f"Forwarding to localhost:{port}")
        print("Ctrl+C to stop\n")

        async with httpx.AsyncClient(follow_redirects=False) as http:
            while True:
                message = await ws.recv()
                data = json.loads(message)

                request_id = data["request_id"]
                method = data["method"]
                path = data["path"]
                body = data["body"]

                # fix host header
                headers = data["headers"]
                headers["host"] = f"localhost:{port}"

                try:
                    response = await http.request(
                        method=method,
                        url=f"http://localhost:{port}/{path}",
                        headers=headers,
                        content=body.encode()
                    )

                    response_headers = dict(response.headers)

                    # remove content-length, FastAPI recalculates it
                    response_headers.pop("content-length", None)
                    response_headers.pop("transfer-encoding", None)  # remove this too just in case

                    # fix redirect location
                    if "location" in response_headers:
                        location = response_headers["location"]
                        if location.startswith("/"):
                            response_headers["location"] = f"/access_int/{subdomain}{location}"

                    # fix asset paths in HTML
                    body_text = response.text
                    content_type = response_headers.get("content-type", "")
                    if "text/html" in content_type:
                        body_text = body_text.replace('href="/', f'href="/access_int/{subdomain}/')
                        body_text = body_text.replace('src="/', f'src="/access_int/{subdomain}/')
                        body_text = body_text.replace("href='/", f"href='/access_int/{subdomain}/")
                        body_text = body_text.replace("src='/", f"src='/access_int/{subdomain}/")

                    await ws.send(json.dumps({
                        "request_id": request_id,
                        "status": response.status_code,
                        "headers": response_headers,
                        "body": body_text
                    }))

                except Exception as e:
                    await ws.send(json.dumps({
                        "request_id": request_id,
                        "status": 502,
                        "headers": {},
                        "body": f"Local server error: {str(e)}"
                    }))

def main():
    if len(sys.argv) != 3:
        print("Usage: tnl <subdomain> <port>")
        print("Example: tnl momboard 5000")
        sys.exit(1)

    subdomain = sys.argv[1]
    port = int(sys.argv[2])

    asyncio.run(run_tunnel(subdomain, port))

if __name__ == "__main__":
    main()