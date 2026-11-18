# VLab UI Automation Toolkit (private research copy)

A small, reusable Windows UI-automation toolkit for a legacy WPF virtual-lab
client. It drives **real mouse/keyboard input** (DPI-aware SendInput), reads
state through **UI Automation** in read-only mode, and uses a fixed absolute
window layout so coordinates are stable and reproducible.

## What is included

- `tools/framework/` — MAA-style pipeline engine, controller, recognition,
  compliance whitelist, calibrated anchors, and the fast fill scripts.
- `tools/workflow/` — offline calculation / field mapping / score estimation /
  local exam audit tools.
- `tools/skill/` — the operational skill: SKILL.md, references (layout,
  pitfalls, interaction physics), and the small input/UIA binaries + sources.
- `data/templates/` — input/output JSON templates.
- `docs/` — framework/runbook/field-map docs (sanitized).

## What is NOT included

- No virtual-lab client binaries, instrument DLLs, `.lab` packages, decompiled
  proprietary sources, exam configuration, or encryption keys.
- No personal data, platform host/IP, account names, screenshots, or logs.

## One-click

Double-click `启动实验.cmd` (or the desktop shortcut) to run the whole flow:
start/reuse the client, pin windows, read truth, fill 101 fields, verify,
submit, audit, and export `data/round_*_oneclick/export/round_data.xlsx` +
`report.html`. `-DoctorOnly` only reports the environment; `-Force` skips the
duplicate-submit confirmation. Each round also writes measurements.csv,
fill_values.csv, and an HTML report.

## Layout (fixed absolute coordinates)

| window | position |
|---|---|
| main | (0, 0) |
| data table | (1900, 0) |
| big view | (1900, 1000) |

Run `python tools/pin_layout.py` (from `tools/framework`) after the client
windows appear, then use the absolute coordinate sheet in
`tools/skill/references/absolute-layout.md`.

## Compliance

This toolkit performs only real UI operations and official-button submission.
Memory inspection, when used, is read-only and for cross-checking. It does not
inject into processes, write memory, modify client files, forge data, or replay
protocol messages. Use only where the course/institution permits automation.
