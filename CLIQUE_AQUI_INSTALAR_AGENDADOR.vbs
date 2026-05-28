Set shell = CreateObject("Shell.Application")
Set fso = CreateObject("Scripting.FileSystemObject")

projectDir = fso.GetParentFolderName(WScript.ScriptFullName)
batPath = projectDir & "\install_scheduled_tasks.bat"

shell.ShellExecute batPath, "", projectDir, "runas", 1
