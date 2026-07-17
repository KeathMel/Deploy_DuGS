#!/usr/bin/env python3
"""
tunnel.py — keep a cloudflared tunnel alive in front of the DUGS API.

Your webhook paths (/hook/... and /resume/...) are already stable. This just
keeps the public door open: it starts cloudflared, and if it ever drops or
crashes, restarts it automatically, with logging.

USAGE
=====
Named tunnel (your own domain — the URL is permanent):
    python3 tunnel.py --name my-tunnel

Quick tunnel (cloudflare gives a random trycloudflare.com URL each start —
fine for testing, NOT stable):
    python3 tunnel.py --url http://localhost:5800

Options:
    --name NAME     run a named tunnel:  cloudflared tunnel run NAME
    --url URL       quick tunnel to URL (default http://localhost:5800)
    --retry SECS    wait this long before restarting after a drop (default 3)
    --cloudflared PATH   path to the cloudflared binary (default: cloudflared)

The named tunnel is the one you want for a permanent link. Set it up once with
cloudflare (cloudflared tunnel create / route dns), then this script keeps it
running forever.

Stop with Ctrl+C.
"""
import argparse
import subprocess
import sys
import time
import datetime
import shutil


def log(msg):
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def build_cmd(args):
    if args.name:
        return [args.cloudflared, "tunnel", "run", args.name]
    return [args.cloudflared, "tunnel", "--url", args.url]


def main():
    ap = argparse.ArgumentParser(description="keep a cloudflared tunnel alive")
    ap.add_argument("--name", help="named tunnel to run (stable URL via your domain)")
    ap.add_argument("--url", default="http://localhost:5800",
                    help="quick-tunnel target (default http://localhost:5800)")
    ap.add_argument("--retry", type=float, default=3.0,
                    help="seconds to wait before restarting after a drop")
    ap.add_argument("--cloudflared", default="cloudflared",
                    help="path to the cloudflared binary")
    args = ap.parse_args()

    if shutil.which(args.cloudflared) is None:
        log(f"ERROR: '{args.cloudflared}' not found on PATH.")
        log("Install it: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/")
        sys.exit(1)

    cmd = build_cmd(args)
    mode = f"named tunnel '{args.name}'" if args.name else f"quick tunnel -> {args.url}"
    log(f"supervising {mode}")
    log(f"command: {' '.join(cmd)}")
    if not args.name:
        log("NOTE: quick tunnels get a NEW random URL each start — not stable.")
        log("      Use --name with your cloudflare domain for a permanent link.")

    restarts = 0
    try:
        while True:
            start = time.time()
            log(f"starting cloudflared{' (restart #' + str(restarts) + ')' if restarts else ''}...")
            try:
                proc = subprocess.Popen(cmd)
                proc.wait()
            except FileNotFoundError:
                log(f"ERROR: could not launch '{args.cloudflared}'."); sys.exit(1)
            except Exception as e:
                log(f"cloudflared launch error: {e}")

            uptime = time.time() - start
            code = proc.returncode if 'proc' in dir() else '?'
            log(f"cloudflared exited (code {code}) after {uptime:.0f}s")

            # if it died almost immediately and repeatedly, back off a bit more
            # so we don't hammer in a tight crash loop
            if uptime < 5:
                backoff = min(args.retry * (1 + restarts), 30)
            else:
                backoff = args.retry
            restarts += 1
            log(f"restarting in {backoff:.0f}s...  (Ctrl+C to stop)")
            time.sleep(backoff)
    except KeyboardInterrupt:
        log("stopped by user.")
        try:
            proc.terminate()
        except Exception:
            pass


if __name__ == "__main__":
    main()
