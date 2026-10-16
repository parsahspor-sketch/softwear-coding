#define AppName "Quiet Hours Monitor"
#define AppVersion "1.0.0"
#define AppPublisher "Quiet Hours Monitor"
#define AppExeName "QuietHoursMonitor.exe"

[Setup]
AppId={{B61BA2ED-53A9-4CD2-9F5C-740937DDA2B4}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={localappdata}\Programs\Quiet Hours Monitor
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=release
OutputBaseFilename=QuietHoursMonitor-Setup
SetupIconFile=QuietHoursMonitor.ico
UninstallDisplayIcon={app}\QuietHoursMonitor.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Files]
Source: "release\{#AppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "QuietHoursMonitor.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\QuietHoursMonitor.ico"; IconIndex: 0
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\QuietHoursMonitor.ico"; IconIndex: 0; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent
