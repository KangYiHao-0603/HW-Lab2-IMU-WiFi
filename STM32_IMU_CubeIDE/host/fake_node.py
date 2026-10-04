#!/usr/bin/env python3
"""Simulates the STM32 board (HTTP POST /sensor_data) so you can test host_gui.py without it.
Usage: python fake_node.py [host] [port]"""
import json, math, random, sys, time, urllib.request

host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
port = int(sys.argv[2]) if len(sys.argv) > 2 else 8080
url = f"http://{host}:{port}/sensor_data"


def post(msg):
    req = urllib.request.Request(url, data=json.dumps(msg).encode(),
                                 headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=2).read()


t0, count, next_ev = time.time(), 0, 5
while True:
    t = time.time() - t0
    post({"type": "data", "t": int(t * 1000),
          "ax": int(200 * math.sin(t)), "ay": int(200 * math.cos(t)), "az": 1000 + random.randint(-20, 20),
          "gx": int(30000 * math.sin(2 * t)), "gy": random.randint(-500, 500), "gz": 0})
    if t > next_ev:
        count += 1
        next_ev += random.uniform(4, 8)
        post({"type": "event", "t": int(t * 1000), "name": "significant_motion", "src": 64, "count": count})
    time.sleep(0.1)
