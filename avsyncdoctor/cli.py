from __future__ import annotations

import argparse
import json
from pathlib import Path

from .core import DEMO, analyze, analyze_media, correct_media, synthesize
from .server import serve


def main() -> None:
    parser = argparse.ArgumentParser(prog="avsyncdoctor")
    sub = parser.add_subparsers(dest="command", required=True)
    analyze_cmd = sub.add_parser("analyze")
    analyze_cmd.add_argument("input")
    inspect_cmd = sub.add_parser("inspect")
    inspect_cmd.add_argument("media")
    synth_cmd = sub.add_parser("synthesize")
    synth_cmd.add_argument("output")
    correct_cmd = sub.add_parser("correct")
    correct_cmd.add_argument("source")
    correct_cmd.add_argument("output")
    sub.add_parser("demo")
    server = sub.add_parser("serve")
    server.add_argument("--host", default="127.0.0.1")
    server.add_argument("--port", type=int, default=8090)
    args = parser.parse_args()
    if args.command == "serve": serve(args.host, args.port); return
    if args.command == "inspect": result = analyze_media(args.media)
    elif args.command == "synthesize": synthesize(args.output); result = {"output": args.output, "inspection": analyze_media(args.output)}
    elif args.command == "correct": result = correct_media(args.source, args.output)
    else:
        payload = DEMO if args.command == "demo" else json.loads(Path(args.input).read_text())
        result = analyze(payload)
    print(json.dumps(result, indent=2))
