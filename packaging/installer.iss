; Inno Setup script for AutoTube Creator v1.0.0
;
; Build with the Inno Setup compiler:
;   ISCC.exe packaging\installer.iss
;
; Produces: AutoTube Creator Setup 1.0.0.exe

#define MyAppName "AutoTube Creator"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "AutoTube Creator"
#define MyAppExeName "autotube.exe"

[Setup]
AppId={{9A7D1E9E-3B48-4C64-9F2C-1D7D2E3A7C21}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\AutoTube Creator
DefaultGroupName=AutoTube Creator
DisableProgramGroupPage=yes
; Per-user install keeps user projects/settings under %APPDATA%\AutoTube.
PrivilegesRequired=lowest
OutputDir=dist
OutputBaseFilename=AutoTube Creator Setup 1.0.0
Compression=lzma
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"; Flags: unchecked

[Files]
Source: "dist\autotube\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Application files only. User data under %APPDATA%\AutoTube is intentionally
; preserved across upgrades and uninstall.
Type: filesandordirs; Name: "{app}\_internal"
Type: files; Name: "{app}\{#MyAppExeName}"
