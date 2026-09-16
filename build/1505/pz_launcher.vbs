Option Explicit
Dim sh, fso, base, post, app, rc
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
base = fso.GetParentFolderName(WScript.ScriptFullName)
post = base & "\post_update.py"
app = base & "\app.py"
If fso.FileExists(post) Then
    rc = sh.Run("pythonw.exe """ & post & """", 0, True)
    On Error Resume Next
    fso.DeleteFile post, True
    On Error GoTo 0
End If
If fso.FileExists(app) Then
    sh.Run "pythonw.exe """ & app & """", 0, False
End If
