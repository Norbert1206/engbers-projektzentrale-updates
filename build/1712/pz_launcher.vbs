Option Explicit
Dim sh, fso, base, post, app, rc, msg
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
base = fso.GetParentFolderName(WScript.ScriptFullName)
post = base & "\post_update.py"
app = base & "\app.py"

If fso.FileExists(post) Then
    rc = sh.Run("pythonw.exe """ & post & """", 0, True)
    If rc = 0 Then
        On Error Resume Next
        fso.DeleteFile post, True
        On Error GoTo 0
    Else
        msg = "Das Projektzentrale-Update konnte nicht vollstaendig installiert werden." & vbCrLf & _
              "Die bisherige Version wird gestartet." & vbCrLf & vbCrLf & _
              "Details: " & base & "\update_1712_error.txt"
        MsgBox msg, 48, "Engbers Projektzentrale - Update"
    End If
End If

If fso.FileExists(app) Then
    sh.Run "pythonw.exe """ & app & """", 0, False
End If
