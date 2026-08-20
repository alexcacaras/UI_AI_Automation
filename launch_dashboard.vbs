Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

projectDir = fso.GetParentFolderName(WScript.ScriptFullName)

pythonExe = projectDir & "\.venv\Scripts\pythonw.exe"
serverFile = projectDir & "\server.py"

' Kill any previous hidden instance so stale code
' cannot stay bound to port 5000.
shell.Run "taskkill /F /IM pythonw.exe", 0, True

' Small pause to release the port.
WScript.Sleep 700

' Start Flask invisibly.
shell.Run """" & pythonExe & """ """ & serverFile & """", 0, False

' Wait for Flask startup.
WScript.Sleep 2500

' Open dashboard.
shell.Run "http://localhost:5000", 1, Falses