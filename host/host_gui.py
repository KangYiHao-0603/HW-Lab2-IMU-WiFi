"""
Host-side HTTP server + real-time GUI for the STM32 IoT node (STM32CubeIDE version).

- HTTP server (default 0.0.0.0:8080) receives  POST /sensor_data  with a JSON body.
- Plots accelerometer (mg) and gyroscope (dps) on live scrolling charts.
- Option 1: shows a red "SIGNIFICANT MOTION" banner + red markers on both
  charts whenever an event message arrives.

Usage:  pip install matplotlib
        python host_gui.py [--port 8080] [--csv log.csv]
Works on Linux (RPi), Windows and macOS.
"""
import argparse
import csv
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import time
from collections import deque

import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

WINDOW_S = 15          # seconds shown on screen
MAXLEN = 2000          # samples kept in memory
BANNER_S = 2.5         # how long the event banner stays visible

lock = threading.Lock()
t0 = time.time()
ts = deque(maxlen=MAXLEN)
acc = {k: deque(maxlen=MAXLEN) for k in ("ax", "ay", "az")}
gyr = {k: deque(maxlen=MAXLEN) for k in ("gx", "gy", "gz")}
events = []            # list of (host_time, count)
status = {"client": None, "last": 0.0}


def handle_msg(msg, writer):
    now = time.time() - t0
    with lock:
        if msg.get("type") == "data":
            ts.append(now)
            for k in acc:
                acc[k].append(msg[k])
            for k in gyr:
                gyr[k].append(msg[k] / 1000.0)   # mdps -> dps
        elif msg.get("type") == "event":
            events.append((now, msg.get("count", len(events) + 1)))
            print(f"[EVENT] {msg.get('name')} #{msg.get('count')} at t={now:.2f}s")
    if writer:
        writer.writerow([f"{now:.3f}", msg.get("type"), json.dumps(msg)])


class Handler(BaseHTTPRequestHandler):
    writer = None

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            msg = json.loads(body)
        except json.JSONDecodeError:
            print("[server] bad body:", body[:80])
            msg = None
        if msg is not None:
            status["client"] = self.client_address[0]
            status["last"] = time.time()
            handle_msg(msg, self.writer)
        try:
            self.send_response(200)
            self.send_header("Content-Length", "2")
            self.end_headers()
            self.wfile.write(b"OK")
        except OSError:
            pass   # the board closes the socket right after sending; that is fine

    def log_message(self, *args):
        pass       # keep the console quiet (one line per POST otherwise)


def server_thread(port, writer):
    Handler.writer = writer

    class Server(ThreadingHTTPServer):
        daemon_threads = True
        # On Windows SO_REUSEADDR lets two programs share one port silently,
        # so turn it off there: a busy port then gives a clear error instead.
        allow_reuse_address = (os.name != "nt")

    try:
        srv = Server(("0.0.0.0", port), Handler)
    except OSError as e:
        print(f"[server] cannot use port {port}: {e}")
        print(f"[server] another program is using it. Close it, or run with another port, e.g. --port 5050")
        os._exit(1)
    print(f"[server] HTTP listening on 0.0.0.0:{port}  (POST /sensor_data)")
    srv.serve_forever()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--csv", help="optional CSV log file")
    ap.add_argument("--demo", action="store_true",
                    help="also start the board simulator (fake_node.py) inside this program")
    args = ap.parse_args()

    writer = None
    if args.csv:
        f = open(args.csv, "w", newline="")
        writer = csv.writer(f)
        writer.writerow(["host_time_s", "type", "raw"])

    threading.Thread(target=server_thread, args=(args.port, writer), daemon=True).start()
    if args.demo:
        import subprocess
        here = os.path.dirname(os.path.abspath(__file__))
        print("[demo] starting fake_node.py -> 127.0.0.1:%d" % args.port)
        demo = subprocess.Popen([sys.executable, os.path.join(here, "fake_node.py"), "127.0.0.1", str(args.port)])
        import atexit
        atexit.register(demo.kill)          # stop the simulator when the GUI window is closed

    fig, (ax1, ax2) = plt.subplots(2, 1, sharex=True, figsize=(10, 6))
    fig.canvas.manager.set_window_title("STM32 IoT node - LSM6DSL monitor")
    colors = {"x": "tab:red", "y": "tab:green", "z": "tab:blue"}
    lines_a = {k: ax1.plot([], [], color=colors[k[1]], label=k[1].upper())[0] for k in acc}
    lines_g = {k: ax2.plot([], [], color=colors[k[1]], label=k[1].upper())[0] for k in gyr}
    ax1.set_ylabel("Accel (mg)")
    ax2.set_ylabel("Gyro (dps)")
    ax2.set_xlabel("time (s)")
    for ax in (ax1, ax2):
        ax.grid(alpha=0.3)
        ax.legend(loc="upper left")

    banner = fig.text(0.5, 0.5, "", ha="center", va="center", fontsize=28,
                      color="white", weight="bold",
                      bbox=dict(facecolor="red", alpha=0.85, boxstyle="round,pad=0.6"))
    banner.set_visible(False)
    info = fig.text(0.99, 0.99, "", ha="right", va="top", fontsize=9)
    drawn_events = set()

    def update(_):
        with lock:
            t = list(ts)
            a = {k: list(v) for k, v in acc.items()}
            g = {k: list(v) for k, v in gyr.items()}
            ev = list(events)
        now = time.time() - t0

        if t:
            for k, ln in lines_a.items():
                ln.set_data(t, a[k])
            for k, ln in lines_g.items():
                ln.set_data(t, g[k])
            right = max(t[-1], WINDOW_S)
            ax1.set_xlim(right - WINDOW_S, right)
            for ax in (ax1, ax2):
                ax.relim()
                ax.autoscale_view(scalex=False)

        # event markers (Option 1)
        for et, cnt in ev:
            if (et, cnt) not in drawn_events:
                drawn_events.add((et, cnt))
                for ax in (ax1, ax2):
                    ax.axvline(et, color="red", lw=2, ls="--", alpha=0.8)
                ax1.annotate(f"SM #{cnt}", xy=(et, 1), xycoords=("data", "axes fraction"),
                             color="red", ha="left", va="top", fontsize=9)

        if ev and now - ev[-1][0] < BANNER_S:
            banner.set_text(f"SIGNIFICANT MOTION  #{ev[-1][1]}")
            banner.set_visible(True)
        else:
            banner.set_visible(False)

        rate = 0.0
        if len(t) > 10:
            rate = (len(t[-20:]) - 1) / max(t[-1] - t[-20:][0], 1e-6)
        online = status["client"] and time.time() - status["last"] < 3
        info.set_text(f"board: {status['client'] if online else 'waiting...'}   "
                      f"rate: {rate:.1f} Hz   events: {len(ev)}")
        return []

    _anim = FuncAnimation(fig, update, interval=50, cache_frame_data=False)
    plt.tight_layout(rect=(0, 0, 1, 0.97))
    plt.show()


if __name__ == "__main__":
    main()