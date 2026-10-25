Option Explicit
Dim sh, fso, dir, py, alvo, rc
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
dir = fso.GetParentFolderName(WScript.ScriptFullName)
py = dir & "\aplicar_traducao.py"

If Not fso.FileExists(py) Then
  MsgBox "Nao achei aplicar_traducao.py na mesma pasta.", 16, "Traducao Elliot"
  WScript.Quit 1
End If

alvo = ""
If WScript.Arguments.Count > 0 Then
  alvo = WScript.Arguments(0)
End If

Function Quoted(s)
  Quoted = Chr(34) & s & Chr(34)
End Function

Function HasExe(name)
  Dim exec, out
  On Error Resume Next
  Set exec = sh.Exec("%comspec% /c where " & name & " 2>nul")
  out = ""
  If Not exec Is Nothing Then out = Trim(exec.StdOut.ReadAll)
  HasExe = (out <> "")
End Function

Dim cmdline
If HasExe("python") Then
  cmdline = "python " & Quoted(py)
ElseIf HasExe("py") Then
  cmdline = "py -3 " & Quoted(py)
Else
  MsgBox "Instale o Python no PC (python.org) e marque Add python.exe to PATH. Depois: pip install pycryptodome", 16, "Traducao Elliot"
  WScript.Quit 1
End If

If alvo <> "" Then cmdline = cmdline & " " & Quoted(alvo)
rc = sh.Run("%comspec% /c " & cmdline, 1, True)
WScript.Quit rc
