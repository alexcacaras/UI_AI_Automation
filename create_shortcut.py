import os
import pathlib
import subprocess

project = pathlib.Path(__file__).resolve().parent
vbs = project / "launch_dashboard.vbs"

# Ask Windows for the actual Desktop path.
powershell = [
    "powershell",
    "-NoProfile",
    "-Command",
    '[Environment]::GetFolderPath("Desktop")'
]

result = subprocess.run(
    powershell,
    capture_output=True,
    text=True,
    check=True
)

desktop = pathlib.Path(result.stdout.strip())

shortcut = desktop / "UI AI Automation.lnk"
temp_ps1 = project / "_create_shortcut.ps1"

icon = project / "branding" / "ui_ai.ico"

lines = [
    '$ws = New-Object -ComObject WScript.Shell',
    f'$s = $ws.CreateShortcut("{shortcut}")',
    '$s.TargetPath = "wscript.exe"',
    f'$s.Arguments = \'""{vbs}""\'',
    f'$s.WorkingDirectory = "{project}"',
    '$s.Description = "UI AI Automation"',
]

if icon.exists():
    lines.append(
        f'$s.IconLocation = "{icon}"'
    )

lines.append('$s.Save()')

temp_ps1.write_text(
    "\n".join(lines),
    encoding="utf-8"
)

os.system(
    f'powershell -ExecutionPolicy Bypass -File "{temp_ps1}"'
)

try:
    temp_ps1.unlink()
except FileNotFoundError:
    pass

print(f"Shortcut created: {shortcut}")