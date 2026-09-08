Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

projectDir = fso.GetParentFolderName(WScript.ScriptFullName)

pythonExe = projectDir & "\.venv\Scripts\pythonw.exe"
serverFile = projectDir & "\server.py"

' Kill any previous hidden instance so stale code
' cannot stay bound to port 5001.
shell.Run "taskkill /F /IM pythonw.exe", 0, True

' Small pause to release the port.
WScript.Sleep 700

' Start Flask invisibly.
shell.Run """" & pythonExe & """ """ & serverFile & """", 0, False

' Wait for Flask startup.
WScript.Sleep 2500

' Open dashboard. Port 5001 is THIS project's — it must match PORT in server.py.
' It used to be 5000, which every other automation project on this machine also
' used, so the browser would open whichever project's server had grabbed the port
' first (usually P2T's dashboard_api.py) while this one silently failed to bind.
shell.Run "http://localhost:5001", 1, False