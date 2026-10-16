# Quiet Hours Monitor

Quiet Hours Monitor is a Windows desktop app that watches system-wide incoming
network traffic and can shut down your PC after a sustained period of low
activity. It is designed for situations such as waiting for a large game or
browser download to finish.

> **Important:** When the configured quiet periods are reached, the app schedules
> a real Windows shutdown. You have 60 seconds to press **Stop** to cancel it.
> Save your work before starting the monitor.

## Features

- Live receive-speed display, sampled every 3 seconds.
- Configurable low-speed threshold, quiet-period duration, and number of quiet
  periods.
- Epic Games, Steam, and Browser Download profiles, each with its own visual
  theme and default threshold and duration.
- A 60-second cancellation window after Windows shutdown is scheduled.
- A standalone Windows executable and optional installer build.

## How it works

The app reads the system-wide received-byte counter and calculates an average
receive speed in KB/s over each 3-second sample. This is not limited to the
selected launcher or browser: other network activity on the PC can affect the
measurement.

When the measured speed is at or below the low-speed threshold for one complete
quiet period, that period is counted. If traffic rises above the threshold, the
current quiet period resets. After the configured number of quiet periods, the
app asks Windows to schedule a shutdown 60 seconds later.

The initial quiet-period count is **3**. Profile defaults are:

| Profile | Low-speed threshold | Quiet period |
| --- | ---: | ---: |
| Epic Games | 50 KB/s | 30 seconds |
| Steam | 70 KB/s | 40 seconds |
| Browser Download | 50 KB/s | 30 seconds |

Choosing a profile applies its theme and resets the threshold and quiet-period
duration to that profile's defaults. You can edit the values and set the number
of quiet periods before starting.

## Run from source

Use Windows and Python with `pip` installed. From the project directory:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python Main.py
```

Keep `QuietHoursMonitor.ico` and `QuietHoursLogoTransparent.png` in the project
directory when running from source; the app loads these assets at startup.

## Use the app

1. Choose **Epic Games**, **Steam**, or **Browser Download**.
2. Review or adjust the low-speed threshold, quiet-period duration, and number
   of quiet periods.
3. Select **Start monitoring**.
4. Watch the live speed, quiet-period progress, and completed-period count.
5. Select **Stop** to stop monitoring. If a shutdown countdown is underway,
   **Stop** also attempts to abort the scheduled Windows shutdown.

The app needs to be running for monitoring. Closing it also attempts to cancel
any shutdown it scheduled. If Windows reports that cancellation failed, the app
shows an error; do not assume the shutdown was canceled.

## Build for Windows

Run the supplied PowerShell script from the project directory:

```powershell
.\build_windows.ps1
```

The script installs the packages in `requirements-build.txt`, generates the
application icon, and builds `release\QuietHoursMonitor.exe`. If Inno Setup is
installed, it also builds `release\QuietHoursMonitor-Setup.exe`. Without Inno
Setup, the standalone executable is still produced.

## Dependencies

- [CustomTkinter](https://customtkinter.tomschimansky.com/) — desktop interface
- [psutil](https://psutil.readthedocs.io/) — network counters
- [Pillow](https://python-pillow.org/) — image loading and splash screen
- [PyInstaller](https://pyinstaller.org/) — Windows application packaging
