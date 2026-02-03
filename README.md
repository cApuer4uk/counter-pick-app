# Counterpick (Dota 2)
Windows-only project (CUDA required).

This repository contains the source code and assets for the Counterpick application.
The application detects picked heroes in Dota 2 and displays counterpicks via an overlay.

The trained YOLO model is included and used directly by the application.

## Virtual environment (optional)
https://drive.google.com/open?id=1hmq-5gsendqnjS6RH9eG-8K-xkdykyQU&authuser=2
---

## Project structure

```
counterpick/ # project root
│
├─ counterpick/ # main package folder
│ │
│ ├─ hero_icons/ # hero icons (jpg)
│ │
│ ├─ weights/ # YOLO weights
│ │ └─ best.pt # trained model
│ │
│ ├─ scripts_for_help/ # application scripts
│ │ ├─ screenshot_windows.py # screenshot capture
│ │ ├─ screenshot_detector.py # YOLO detection logic
│ │ ├─ overlay_window.py # overlay rendering
│ │ ├─ gui_launcher.py # GUI launcher
│ │ └─ script_compilation_installer.iss
│ │
│ ├─ tests/ # tests (smoke / integration)
│ │ ├─ fixtures/
│ │ └─ test_*.py
│ │
│ └─ overlay_data.json # runtime file (not tracked by git)
│
└─ README.md
```