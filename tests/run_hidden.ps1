# Run FreeCAD on a separate, never-shown Windows desktop and wait for it.
# The window renders normally (OpenGL included), so widget grabs and the
# self-test work, but nothing appears on your screen and nothing takes focus.
# The test script must close its documents and quit FreeCAD itself.
# Usage: tests\run_hidden.ps1 -UserCfg <copy of user.cfg> -Script <test.py> [-TimeoutSec 150] [-Exe <freecad.exe>]
param(
    [Parameter(Mandatory = $true)][string]$UserCfg,
    [Parameter(Mandatory = $true)][string]$Script,
    [int]$TimeoutSec = 150,
    [string]$Exe = "$env:LOCALAPPDATA\Programs\FreeCAD 1.1\bin\freecad.exe"
)

if (-not ("HiddenDesktop" -as [type])) {
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;

public static class HiddenDesktop {
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    struct STARTUPINFO {
        public int cb; public string lpReserved; public string lpDesktop; public string lpTitle;
        public int dwX, dwY, dwXSize, dwYSize, dwXCountChars, dwYCountChars, dwFillAttribute, dwFlags;
        public short wShowWindow, cbReserved2; public IntPtr lpReserved2, hStdInput, hStdOutput, hStdError;
    }
    [StructLayout(LayoutKind.Sequential)]
    struct PROCESS_INFORMATION { public IntPtr hProcess, hThread; public int dwProcessId, dwThreadId; }

    [DllImport("user32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    static extern IntPtr CreateDesktop(string name, IntPtr device, IntPtr devmode, int flags, uint access, IntPtr sa);
    [DllImport("user32.dll", SetLastError = true)]
    static extern bool CloseDesktop(IntPtr desktop);
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    static extern bool CreateProcess(string app, string cmd, IntPtr pa, IntPtr ta, bool inherit, int flags,
                                     IntPtr env, string dir, ref STARTUPINFO si, out PROCESS_INFORMATION pi);
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern uint WaitForSingleObject(IntPtr handle, uint ms);
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern bool TerminateProcess(IntPtr handle, uint code);
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern bool GetExitCodeProcess(IntPtr handle, out uint code);
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern bool CloseHandle(IntPtr handle);

    // Returns the exit code, or -1 when it had to be killed.
    public static long Run(string commandLine, string dir, uint timeoutMs) {
        IntPtr desk = CreateDesktop("OpenRefreshTests", IntPtr.Zero, IntPtr.Zero, 0, 0x10000000, IntPtr.Zero);
        if (desk == IntPtr.Zero) throw new System.ComponentModel.Win32Exception();
        try {
            var si = new STARTUPINFO();
            si.cb = Marshal.SizeOf(si);
            si.lpDesktop = "OpenRefreshTests";
            PROCESS_INFORMATION pi;
            if (!CreateProcess(null, commandLine, IntPtr.Zero, IntPtr.Zero, false, 0, IntPtr.Zero, dir, ref si, out pi))
                throw new System.ComponentModel.Win32Exception();
            long result;
            if (WaitForSingleObject(pi.hProcess, timeoutMs) != 0) {
                TerminateProcess(pi.hProcess, 1);
                WaitForSingleObject(pi.hProcess, 10000);
                result = -1;
            } else {
                uint code; GetExitCodeProcess(pi.hProcess, out code); result = code;
            }
            CloseHandle(pi.hThread); CloseHandle(pi.hProcess);
            return result;
        } finally {
            CloseDesktop(desk);
        }
    }
}
"@
}

$cmd = "`"$Exe`" --user-cfg `"$UserCfg`" `"$Script`""
$code = [HiddenDesktop]::Run($cmd, (Split-Path $Exe), [uint32]($TimeoutSec * 1000))
if ($code -eq -1) { "FreeCAD timed out after $TimeoutSec s and was stopped" } else { "FreeCAD exited with code $code" }
