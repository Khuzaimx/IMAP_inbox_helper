; =============================================================================
; InboxHelper - Professional Inno Setup Installation Script
; =============================================================================
#define MyAppName "InboxHelper"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Khuzaimx"
#define MyAppExeName "main.exe"

[Setup]
; App Metadata
AppId={{D37F2F11-48C0-46BE-903D-9DE7764D509C}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}

; Output Configuration
OutputDir=dist
OutputBaseFilename=InboxHelper_Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

; Icon Mapping
SetupIconFile=ui\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startup"; Description: "Launch InboxHelper automatically when turning on PC"; GroupDescription: "Windows Startup Integration:"

[Files]
; Copy all compiled PyInstaller folder assets recursively
Source: "dist\main\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
; Start Menu and Desktop Shortcuts
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
; Standard Windows Run key to execute the app automatically on turning on the laptop
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "{#MyAppName}"; ValueData: """{app}\{#MyAppExeName}"""; Tasks: startup; Flags: uninsdeletevalue

[Run]
; Option to immediately launch the app upon completing installation
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
