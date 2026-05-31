# SharePoint Gantt Chart Integration

Options and implementation steps for publishing a Gantt/schedule chart from the UnitTracker app to a SharePoint homepage as a static image.

---

## Context & Constraints

- **App type**: PyQt5 desktop EXE, no server/backend
- **Data source**: Excel workbook (`excel_path` in `config.yaml`), already parsed into `Unit` dataclass objects by `data/loader.py`
- **SharePoint access**: None currently — requires IT to provision an Azure AD app registration
- **Target**: Static PNG image displayed on a SharePoint homepage via the Image web part
- **Scheduling**: Windows Task Scheduler (no backend), or triggered manually from the GUI

---

## Options at a Glance

| Option | Auth model | Scheduling | Interactive? | IT lift |
|--------|-----------|------------|--------------|---------|
| [A] Delegated (interactive login) | User SSO, cached token | Task Scheduler (token seeded once) | No | Low |
| [B] App-only (client secret) | Service principal | Full silent/unattended | No | Medium |
| [C] Manual copy to network share | None | Manual or Task Scheduler | No | None |

All three options produce the same end result: a PNG file on SharePoint displayed by an Image web part. The options differ only in *how* the file gets there.

---

## Option A — Delegated Auth (Recommended Starting Point)

The app uses MSAL interactive login the first time, caches the token locally, and silently refreshes it on subsequent runs. The user running the app needs write access to the target SharePoint document library.

**Best for**: Getting started quickly; token seeded once by whoever runs the app daily.

### What IT needs to provide (one-time)

- Register an Azure AD app (type: **Public client / native**)
- Grant **delegated** permissions: `Files.ReadWrite` and `Sites.ReadWrite.All`
- Provide: `tenant_id`, `client_id`, SharePoint site URL or `site_id`, drive/library ID, target file path

### `config.yaml` additions

```yaml
sharepoint:
  enabled: false                          # flip to true when credentials are ready
  tenant_id: "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
  client_id: "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
  drive_id:  "b!xxxxxxxxxxxxxxxxxxxx"     # document library drive ID
  upload_path: "Shared Documents/schedule_gantt.png"
  token_cache_path: "sp_token_cache.bin"  # local encrypted token cache
```

### New module: `automation/sharepoint_upload.py`

```python
"""
SharePoint upload helper — delegates auth to MSAL and file upload to Graph API.
Called by the Gantt export pipeline after chart generation.
"""
import os
import msal
import requests

TOKEN_SCOPES = ["https://graph.microsoft.com/Files.ReadWrite",
                "https://graph.microsoft.com/Sites.ReadWrite.All"]

def _build_msal_app(cfg: dict) -> msal.PublicClientApplication:
    cache = msal.SerializableTokenCache()
    cache_path = cfg.get("token_cache_path", "sp_token_cache.bin")
    if os.path.exists(cache_path):
        cache.deserialize(open(cache_path, "r").read())
    app = msal.PublicClientApplication(
        cfg["client_id"],
        authority=f"https://login.microsoftonline.com/{cfg['tenant_id']}",
        token_cache=cache,
    )
    return app, cache, cache_path

def acquire_token(cfg: dict) -> str:
    """Returns a valid access token; opens browser login prompt if needed."""
    app, cache, cache_path = _build_msal_app(cfg)
    accounts = app.get_accounts()
    result = None
    if accounts:
        result = app.acquire_token_silent(TOKEN_SCOPES, account=accounts[0])
    if not result:
        result = app.acquire_token_interactive(scopes=TOKEN_SCOPES)
    if "access_token" not in result:
        raise RuntimeError(f"MSAL auth failed: {result.get('error_description')}")
    # Persist updated cache
    open(cache_path, "w").write(cache.serialize())
    return result["access_token"]

def upload_png(png_path: str, cfg: dict) -> bool:
    """Uploads png_path to the configured SharePoint document library. Returns True on success."""
    token = acquire_token(cfg)
    upload_url = (
        f"https://graph.microsoft.com/v1.0"
        f"/drives/{cfg['drive_id']}/items/root:/{cfg['upload_path']}:/content"
    )
    with open(png_path, "rb") as f:
        resp = requests.put(
            upload_url,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "image/png"},
            data=f,
        )
    resp.raise_for_status()
    return True
```

---

## Option B — App-Only Auth (Unattended / Task Scheduler)

Uses a client secret stored in `config.yaml`. No login prompt — runs silently even when no user is present. Requires IT to grant **application-level** SharePoint permissions (broader than delegated; requires admin consent).

**Best for**: Full automation; scheduled runs with no human interaction required.

### Additional `config.yaml` field

```yaml
sharepoint:
  # ... same fields as Option A, plus:
  client_secret: "your-client-secret-here"   # keep out of source control
```

### Auth change in `sharepoint_upload.py`

Replace `_build_msal_app` / `acquire_token` with:

```python
def acquire_token(cfg: dict) -> str:
    app = msal.ConfidentialClientApplication(
        cfg["client_id"],
        authority=f"https://login.microsoftonline.com/{cfg['tenant_id']}",
        client_credential=cfg["client_secret"],
    )
    result = app.acquire_token_for_client(
        scopes=["https://graph.microsoft.com/.default"]
    )
    if "access_token" not in result:
        raise RuntimeError(f"MSAL auth failed: {result.get('error_description')}")
    return result["access_token"]
```

> **Security note**: Do not commit `client_secret` to source control. Consider loading it from an environment variable (`os.environ["SP_CLIENT_SECRET"]`) and documenting that in `config.yaml` as a comment.

---

## Option C — Manual / Network Share (No IT dependency)

If SharePoint auth is not feasible in the short term, the PNG can be saved to a network share or SharePoint-synced folder (OneDrive sync client). A SharePoint Image web part can reference a file in a synced library directly.

**Best for**: Zero IT dependency; proof-of-concept while waiting for app registration.

**Limitation**: Requires the machine running the app to have the target folder synced locally, and the SharePoint Image web part URL must point to the SharePoint-hosted copy (not the local path).

No new auth module needed — just write the PNG to the synced folder path.

---

## Chart Generation: `automation/gantt_export.py`

Regardless of which upload option is used, chart generation is the same. This new module reads the already-loaded `Unit` list and produces a PNG using `matplotlib`.

```python
"""
Gantt chart export pipeline.
Reads units via the existing loader, renders a PNG, optionally uploads to SharePoint.
"""
import matplotlib
matplotlib.use("Agg")   # headless — no Qt window
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.dates as mdates
from datetime import date, timedelta
from data.loader import load_units
from data.models import Unit

STATUS_COLORS = {
    "green":  "#4CAF50",
    "yellow": "#FFC107",
    "red":    "#F44336",
    "gray":   "#9E9E9E",
    "orange": "#FF9800",
    "purple": "#9C27B0",
}

def generate_gantt_png(units: list[Unit], output_path: str, title: str = "Schedule") -> str:
    """
    Renders a horizontal Gantt chart from a list of Units and saves to output_path.
    Uses detailing_due_date as the bar end; unit_detailing_start_date as bar start.
    Falls back to today ± 7 days if dates are missing.
    Returns output_path.
    """
    today = date.today()
    # Filter to units with at least one date
    chartable = [u for u in units if u.detailing_due_date or u.unit_detailing_start_date]
    if not chartable:
        raise ValueError("No units with date data available for Gantt chart.")

    fig_height = max(4, len(chartable) * 0.45 + 1.5)
    fig, ax = plt.subplots(figsize=(14, fig_height))

    for i, unit in enumerate(reversed(chartable)):
        start = unit.unit_detailing_start_date or (unit.detailing_due_date - timedelta(days=14))
        end   = unit.detailing_due_date or (unit.unit_detailing_start_date + timedelta(days=14))
        color = STATUS_COLORS.get(unit.calculated_status_color, "#9E9E9E")
        ax.barh(i, (end - start).days, left=mdates.date2num(start),
                height=0.6, color=color, alpha=0.85, edgecolor="white", linewidth=0.5)
        label = f"{unit.com_number}  {unit.job_name[:28]}"
        ax.text(mdates.date2num(start) + 0.5, i, label,
                va="center", ha="left", fontsize=7, color="white", fontweight="bold")

    # TODAY line
    ax.axvline(mdates.date2num(today), color="black", linewidth=1.5, linestyle="--", alpha=0.7, label="Today")

    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=0, interval=2))
    plt.xticks(rotation=30, ha="right", fontsize=8)
    ax.set_yticks([])
    ax.set_title(title, fontsize=13, fontweight="bold", pad=10)
    ax.set_xlabel("Date", fontsize=9)

    # Legend
    legend_patches = [mpatches.Patch(color=v, label=k.capitalize()) for k, v in STATUS_COLORS.items()]
    legend_patches.append(mpatches.Patch(color="black", label="Today"))
    ax.legend(handles=legend_patches, loc="lower right", fontsize=7, ncol=3)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return output_path


def export_and_upload(config: dict) -> str:
    """
    Full pipeline: load units → generate PNG → upload to SharePoint (if enabled).
    Returns a status message string.
    """
    sp_cfg = config.get("sharepoint", {})
    output_path = config.get("gantt_output_path", "gantt_output.png")
    title = config.get("gantt_title", "Detailing Schedule")

    units = load_units(
        config["excel_path"],
        config["sheet_name"],
        config.get("detailer_schedules", {}),
        force_reload=False,
    )
    generate_gantt_png(units, output_path, title=title)

    if not sp_cfg.get("enabled", False):
        return f"Chart saved to {output_path} (SharePoint upload disabled in config)."

    from automation.sharepoint_upload import upload_png
    upload_png(output_path, sp_cfg)
    return f"Chart uploaded to SharePoint: {sp_cfg['upload_path']}"
```

---

## Wiring into the Existing App

### 1. Add `config.yaml` fields

```yaml
# Gantt export
gantt_output_path: "gantt_output.png"
gantt_title: "Detailing Schedule"

# SharePoint (leave enabled: false until credentials are ready)
sharepoint:
  enabled: false
  tenant_id: ""
  client_id: ""
  drive_id:  ""
  upload_path: "Shared Documents/schedule_gantt.png"
  token_cache_path: "sp_token_cache.bin"
  # client_secret: ""   # Option B only — prefer env var SP_CLIENT_SECRET
```

### 2. Register the new macro (Option: add to GUI dropdown)

In `automation/vba_runner.py`, add to `MACRO_DISPATCH`:

```python
from automation.gantt_export import export_and_upload

MACRO_DISPATCH = {
    # ... existing entries ...
    "ExportGantt": lambda path: export_and_upload(config),  # pass config through
}
```

Then add `"ExportGantt"` to the `macros` list in `config.yaml`.

### 3. Add a dedicated toolbar button (alternative)

In `gui/main_window.py`, add an "Export Gantt" button alongside the existing Pull CSV and Refresh buttons. Wire it to a `GanttWorker(QThread)` that calls `export_and_upload(self.config)` in the background — same pattern as `LoadWorker` and `SaveWorker`.

---

## Windows Task Scheduler (Scheduled Export)

To run the export on a schedule without the full GUI, add a CLI entry point to `main.py` or a new `export_cli.py`:

```python
# export_cli.py
import yaml
from automation.gantt_export import export_and_upload

if __name__ == "__main__":
    config = yaml.safe_load(open("config.yaml"))
    print(export_and_upload(config))
```

**Task Scheduler settings:**

| Field | Value |
|---|---|
| Program | `path\to\UnitTracker.exe` or `python.exe` |
| Arguments | `export_cli.py` (if using Python) or a `--export-gantt` flag |
| Start in | Directory containing `config.yaml` |
| Trigger | Daily at a fixed time (e.g., 7:00 AM) |
| Run whether user logged on or not | Option B only (app-only auth) |

> For Option A (delegated), the task must run **while the user is logged in**, since the cached token is user-scoped. The first run requires an interactive login to seed the cache.

---

## SharePoint Homepage Setup (One-Time, Done by Site Owner)

1. Upload the PNG to the target document library (first run of the app does this).
2. Edit the SharePoint homepage.
3. Add an **Image** web part.
4. Set the image source to the file URL in the document library (e.g., `https://yourorg.sharepoint.com/sites/yoursite/Shared%20Documents/schedule_gantt.png`).
5. Save/publish the page.

After this one-time setup, every subsequent app run that overwrites the file will automatically update the displayed image — no further SharePoint changes needed.

---

## New Dependencies

Add to `requirements.txt`:

```
matplotlib>=3.7
msal>=1.24        # Option A or B only
requests>=2.31    # Option A or B only
```

`matplotlib` has no system dependencies and bundles cleanly with PyInstaller. `msal` and `requests` also bundle without issues.

### PyInstaller (`UnitTracker.spec`) — hidden imports to add

```python
hiddenimports=["msal", "msal.application", "msal.token_cache",
               "matplotlib", "matplotlib.backends.backend_agg"]
```

---

## Implementation Order

1. Add `matplotlib` and implement `automation/gantt_export.py` — testable with no SharePoint access.
2. Add `gantt_output_path` / `gantt_title` to `config.yaml`.
3. Wire a GUI button or macro entry to trigger the export locally — confirm PNG output.
4. Engage IT for Azure AD app registration (Option A request is low-lift).
5. Add `automation/sharepoint_upload.py`, fill SharePoint fields in `config.yaml`, flip `enabled: true`.
6. Seed the MSAL token cache with one interactive run; confirm upload.
7. Set up Task Scheduler entry if scheduled export is desired.
8. Have the SharePoint site owner add the Image web part (one-time).
