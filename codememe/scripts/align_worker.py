#!/usr/bin/env python3
"""Runs in the faster-whisper environment: prints {wav path: [[word, start, end], ...]} for each wav given.
Deliberately imports nothing from codememe."""

import argparse
import json
import sys

from faster_whisper import WhisperModel

parser = argparse.ArgumentParser()
parser.add_argument("--model", required=True)
parser.add_argument("files", nargs="+")
args = parser.parse_args()
try:
    model = WhisperModel(args.model, device="cuda", compute_type="float16")
except Exception:
    model = WhisperModel(args.model, device="cpu", compute_type="int8")
result = {}
for path in args.files:
    segments, _ = model.transcribe(path, language="en", word_timestamps=True, beam_size=1, vad_filter=False)
    result[path] = [[w.word.strip(), round(w.start, 3), round(w.end, 3)] for s in segments for w in (s.words or [])]
sys.stdout.write(json.dumps(result))
