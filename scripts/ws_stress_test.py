"""
WebSocket Stress Test for PitchSense.

This is a standalone asyncio script (no locust dependency) that hammers the
WebSocket endpoint with concurrent connections, pitches, and reconnects.

Answers:
    - How many concurrent WS connections can Daphne handle?
    - What happens under reconnect storms?
    - Do message bursts cause dropped messages?

Usage:
    1. Start the dev server:  python manage.py runserver 8000
    2. Create test users:     python manage.py shell
                              >>> from django.contrib.auth.models import User
                              >>> for i in range(50):
                              ...     User.objects.create_user(f'wstest{i}@test.com', password='Test123!!')
    3. Run:                   python scripts/ws_stress_test.py --users 20 --host ws://127.0.0.1:8000

Metrics reported:
    - Connections succeeded/failed
    - Message send/receive latency
    - Reconnection success rate
    - Total messages exchanged
"""
import asyncio
import json
import time
import uuid
import argparse
import logging
from dataclasses import dataclass, field

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

try:
    import websockets
except ImportError:
    print("Install websockets: pip install websockets")
    exit(1)

try:
    import httpx
except ImportError:
    print("Install httpx: pip install httpx")
    exit(1)


@dataclass
class StressMetrics:
    connections_attempted: int = 0
    connections_succeeded: int = 0
    connections_failed: int = 0
    messages_sent: int = 0
    messages_received: int = 0
    errors: int = 0
    reconnects: int = 0
    latencies: list = field(default_factory=list)

    def report(self):
        avg_lat = sum(self.latencies) / len(self.latencies) if self.latencies else 0
        p95_lat = sorted(self.latencies)[int(len(self.latencies) * 0.95)] if self.latencies else 0
        print("\n" + "=" * 60)
        print("WebSocket Stress Test Results")
        print("=" * 60)
        print(f"  Connections attempted:  {self.connections_attempted}")
        print(f"  Connections succeeded:  {self.connections_succeeded}")
        print(f"  Connections failed:     {self.connections_failed}")
        print(f"  Messages sent:          {self.messages_sent}")
        print(f"  Messages received:      {self.messages_received}")
        print(f"  Errors:                 {self.errors}")
        print(f"  Reconnects:             {self.reconnects}")
        print(f"  Avg latency:            {avg_lat*1000:.1f}ms")
        print(f"  P95 latency:            {p95_lat*1000:.1f}ms")
        print("=" * 60)

        if self.connections_failed > 0:
            print(f"\n⚠️  {self.connections_failed} connections failed — Daphne may be at capacity")
        if p95_lat > 1.0:
            print(f"\n⚠️  P95 latency > 1s — server is under heavy load")
        if self.errors > 0:
            print(f"\n⚠️  {self.errors} errors during test")


metrics = StressMetrics()


async def login_and_get_cookies(http_base: str, username: str, password: str) -> dict:
    """Login via HTTP and return session cookies for WS auth."""
    async with httpx.AsyncClient(base_url=http_base) as client:
        # Get CSRF token
        resp = await client.get("/api/csrf/")
        csrf_token = resp.cookies.get("csrftoken", "")
        cookies = dict(resp.cookies)

        # Login
        resp = await client.post(
            "/api/login/",
            json={"username": username, "password": password},
            headers={"X-CSRFToken": csrf_token},
            cookies=cookies,
        )
        cookies.update(resp.cookies)

        if resp.status_code != 200:
            raise Exception(f"Login failed for {username}: {resp.status_code}")

        return cookies


async def simulate_user(ws_base: str, http_base: str, user_idx: int, num_pitches: int = 2):
    """Simulate a single user: login, connect WS, send pitches, disconnect."""
    username = f"wstest{user_idx}@test.com"
    password = "Test123!!"
    session_id = str(uuid.uuid4())

    try:
        cookies = await login_and_get_cookies(http_base, username, password)
    except Exception as e:
        logger.error(f"User {user_idx}: login failed: {e}")
        metrics.connections_failed += 1
        return

    cookie_header = "; ".join(f"{k}={v}" for k, v in cookies.items())
    ws_url = f"{ws_base}/ws/debate/{session_id}/"

    metrics.connections_attempted += 1

    try:
        async with websockets.connect(
            ws_url,
            additional_headers={"Cookie": cookie_header, "Origin": http_base},
            open_timeout=10,
            close_timeout=5,
        ) as ws:
            metrics.connections_succeeded += 1

            # Read connection_established
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
            metrics.messages_received += 1
            assert msg["type"] == "connection_established", f"Unexpected: {msg['type']}"
            logger.info(f"User {user_idx}: connected, session={session_id[:8]}")

            # Send pitches
            for pitch_num in range(num_pitches):
                if pitch_num > 0:
                    await asyncio.sleep(3.5)  # Respect cooldown

                pitch = {
                    "type": "user_pitch",
                    "content": f"Stress test pitch #{pitch_num} from user {user_idx}. "
                               f"We are building a {uuid.uuid4().hex[:8]} platform.",
                    "target": "all",
                    "mode": "panel",
                }

                send_time = time.time()
                await ws.send(json.dumps(pitch))
                metrics.messages_sent += 1

                # Collect responses until turn_complete
                first_response = True
                while True:
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=30)
                        data = json.loads(raw)
                        metrics.messages_received += 1

                        if first_response:
                            latency = time.time() - send_time
                            metrics.latencies.append(latency)
                            first_response = False

                        if data["type"] == "turn_complete":
                            logger.info(
                                f"User {user_idx}: pitch {pitch_num} complete, "
                                f"turn={data.get('current_turn')}"
                            )
                            break
                        elif data["type"] == "error":
                            logger.warning(f"User {user_idx}: error: {data['message']}")
                            metrics.errors += 1
                            break

                    except asyncio.TimeoutError:
                        logger.error(f"User {user_idx}: timeout waiting for response")
                        metrics.errors += 1
                        break

            # Test ping/pong
            await ws.send(json.dumps({"type": "ping"}))
            metrics.messages_sent += 1
            pong = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
            metrics.messages_received += 1
            assert pong["type"] == "pong"

    except (websockets.exceptions.ConnectionClosed, ConnectionRefusedError) as e:
        logger.error(f"User {user_idx}: WS connection failed: {e}")
        metrics.connections_failed += 1
        metrics.errors += 1
    except Exception as e:
        logger.error(f"User {user_idx}: unexpected error: {e}")
        metrics.connections_failed += 1
        metrics.errors += 1


async def reconnect_storm(ws_base: str, http_base: str, num_reconnects: int = 10):
    """Simulate a reconnect storm: rapid disconnect/reconnect cycles."""
    username = "wstest0@test.com"
    password = "Test123!!"

    try:
        cookies = await login_and_get_cookies(http_base, username, password)
    except Exception as e:
        logger.error(f"Reconnect storm: login failed: {e}")
        return

    cookie_header = "; ".join(f"{k}={v}" for k, v in cookies.items())
    session_id = str(uuid.uuid4())
    ws_url = f"{ws_base}/ws/debate/{session_id}/"

    for i in range(num_reconnects):
        try:
            async with websockets.connect(
                ws_url,
                additional_headers={"Cookie": cookie_header, "Origin": http_base},
                open_timeout=5,
            ) as ws:
                msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
                metrics.reconnects += 1
                # Disconnect immediately
        except Exception:
            metrics.errors += 1

    logger.info(f"Reconnect storm: {metrics.reconnects}/{num_reconnects} succeeded")


async def main(args):
    ws_base = args.host.replace("http://", "ws://").replace("https://", "wss://")
    http_base = args.host.replace("ws://", "http://").replace("wss://", "https://")

    print(f"\n🔥 PitchSense WebSocket Stress Test")
    print(f"   Target:       {args.host}")
    print(f"   Users:        {args.users}")
    print(f"   Pitches/user: {args.pitches}")
    print(f"   Reconnects:   {args.reconnects}")
    print()

    # Phase 1: Concurrent users
    logger.info(f"Phase 1: Spawning {args.users} concurrent users...")
    tasks = [
        simulate_user(ws_base, http_base, i, args.pitches)
        for i in range(args.users)
    ]
    await asyncio.gather(*tasks, return_exceptions=True)

    # Phase 2: Reconnect storm
    if args.reconnects > 0:
        logger.info(f"Phase 2: Reconnect storm ({args.reconnects} cycles)...")
        await reconnect_storm(ws_base, http_base, args.reconnects)

    metrics.report()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PitchSense WebSocket Stress Test")
    parser.add_argument("--host", default="ws://127.0.0.1:8000", help="Server URL")
    parser.add_argument("--users", type=int, default=10, help="Concurrent users")
    parser.add_argument("--pitches", type=int, default=1, help="Pitches per user")
    parser.add_argument("--reconnects", type=int, default=10, help="Reconnect storm cycles")
    args = parser.parse_args()

    asyncio.run(main(args))
