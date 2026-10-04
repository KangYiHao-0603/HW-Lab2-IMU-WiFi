"""Simulates the STM32 board (HTTP POST /sensor_data) so you can test host_gui.py without it.
Usage: py fake_node.py [host] [port]
Start host_gui.py FIRST, in another window, and keep it open."""
import json, math, random, sys, time, urllib.error, urllib.request

host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
port = int(sys.argv[2]) if len(sys.argv) > 2 else 8080
url = f"http://{host}:{port}/sensor_data"
# ignore any system proxy setting (a proxy can make even 127.0.0.1 time out)
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def post(msg):
    req = urllib.request.Request(url, data=json.dumps(msg).encode(),
                                 headers={"Content-Type": "application/json"})
    opener.open(req, timeout=5).read()


print(f"sending to {url}  (Ctrl+C to stop)")
t0, count, next_ev, sent, last_err = time.time(), 0, 5, 0, 0
while True:
    t = time.time() - t0
    try:
        post({"type": "data", "t": int(t * 1000),
              "ax": int(200 * math.sin(t)), "ay": int(200 * math.cos(t)), "az": 1000 + random.randint(-20, 20),
              "gx": int(30000 * math.sin(2 * t)), "gy": random.randint(-500, 500), "gz": 0})
        sent += 1
        if sent == 1:
            print("OK: host_gui is receiving data")
        if t > next_ev:
            count += 1
            next_ev += random.uniform(4, 8)
            post({"type": "event", "t": int(t * 1000), "name": "significant_motion", "src": 64, "count": count})
            print(f"sent event #{count}")
    except (urllib.error.URLError, OSError) as e:
        if time.time() - last_err > 2:
            last_err = time.time()
            print(f"cannot reach {host}:{port}: {getattr(e, 'reason', e)}  -> is host_gui.py running?")
        time.sleep(0.5)
        continue
    time.sleep(0.1)