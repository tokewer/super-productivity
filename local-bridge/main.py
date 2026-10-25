"""
Super Productivity Enhanced Local Bridge - Main Runner
Runs HTTP bridge server and optional Mini Timer Window concurrently.
"""

import sys
import os
import argparse
import threading
import logging
from bridge_server import start_server, load_or_create_config, logger
from mini_window import run_mini_window


def parse_args():
    parser = argparse.ArgumentParser(description="Super Productivity Enhanced Local Bridge")
    parser.add_argument("--server-only", action="store_true", help="Run only the background HTTP server without GUI")
    parser.add_argument("--gui-only", action="store_true", help="Run only the Mini Timer GUI window")
    parser.add_argument("--port", type=int, default=None, help="Override HTTP port (default: 4567)")
    parser.add_argument("--verify", action="store_true", help="Verify all existing backups integrity and exit")
    return parser.parse_args()


def main():
    args = parse_args()
    cfg = load_or_create_config()

    if args.verify:
        from backup_manager import BackupManager
        bm = BackupManager(cfg.get("backup_dir", os.path.join(os.path.dirname(__file__), "backups")))
        backups = bm.list_backups()
        print(f"Checking {len(backups)} backups in {bm.backup_dir}...")
        valid = 0
        for b in backups:
            ok, msg = bm.verify_integrity(b["filename"])
            status = "PASS" if ok else "FAIL"
            print(f"[{status}] {b['filename']} -> {msg}")
            if ok:
                valid += 1
        print(f"Summary: {valid}/{len(backups)} valid.")
        sys.exit(0 if valid == len(backups) else 1)

    if args.gui_only:
        print("Starting Mini Timer Window only...")
        run_mini_window()
        return

    # Start HTTP Bridge Server
    server = start_server(port=args.port, config=cfg)

    if args.server_only:
        print(f"Running Bridge Server in foreground on http://127.0.0.1:{cfg.get('port', 4567)}")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("Shutting down...")
            server.server_close()
        return

    # Default: Run server in background thread, run GUI in main thread
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    print(f"Bridge server started on http://127.0.0.1:{cfg.get('port', 4567)}")
    print("Launching Mini Timer Window...")

    try:
        run_mini_window()
    finally:
        server.shutdown()
        server.server_close()
        print("Bridge stopped cleanly.")


if __name__ == "__main__":
    main()
