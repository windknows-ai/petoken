; Petoken one-click installer (Inno Setup 6).
; Built by build.ps1 -Installer, or by hand:
;   ISCC.exe /DAppVersion=1.7.0 /DSourceDir=dist\petoken /DOutputDir=dist installer\petoken.iss
; Installs per user (no administrator rights) into %LOCALAPPDATA%\Programs\Petoken,
; adds Start menu / optional desktop shortcuts and an uninstaller. Settings and
; workbench data in %LOCALAPPDATA%\CodexWisp are kept on uninstall.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef SourceDir
  #define SourceDir "..\dist\petoken"
#endif
#ifndef OutputDir
  #define OutputDir "..\dist"
#endif

[Setup]
AppId={{6E7C2F3A-3B57-4E4B-9A55-5C1D2B1F7A11}
AppName=Petoken
AppVersion={#AppVersion}
AppVerName=Petoken {#AppVersion}
AppPublisher=windknows-ai
AppPublisherURL=https://github.com/windknows-ai/petoken
AppSupportURL=https://github.com/windknows-ai/petoken/issues
AppUpdatesURL=https://github.com/windknows-ai/petoken/releases
DefaultDirName={localappdata}\Programs\Petoken
DisableProgramGroupPage=yes
DisableDirPage=auto
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#OutputDir}
OutputBaseFilename=Petoken-Setup-v{#AppVersion}
SetupIconFile=..\assets\petoken.ico
UninstallDisplayIcon={app}\petoken.exe
UninstallDisplayName=Petoken
WizardStyle=modern
Compression=lzma2/ultra64
SolidCompression=yes
; Close a running Petoken before files are replaced (upgrades).
CloseApplications=yes
RestartApplications=no
LicenseFile={#SourceDir}\LICENSE

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "startup"; Description: "Start Petoken when Windows starts"; GroupDescription: "Startup:"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Petoken"; Filename: "{app}\petoken.exe"
Name: "{autodesktop}\Petoken"; Filename: "{app}\petoken.exe"; Tasks: desktopicon
Name: "{userstartup}\Petoken"; Filename: "{app}\petoken.exe"; Tasks: startup

[Run]
Filename: "{app}\petoken.exe"; Description: "{cm:LaunchProgram,Petoken}"; Flags: nowait postinstall skipifsilent
; Petoken's own one-click update runs the installer silently with /RELAUNCH=1.
Filename: "{app}\petoken.exe"; Flags: nowait; Check: WantRelaunch

[Code]
function WantRelaunch: Boolean;
begin
  Result := ExpandConstant('{param:RELAUNCH|0}') = '1';
end;
