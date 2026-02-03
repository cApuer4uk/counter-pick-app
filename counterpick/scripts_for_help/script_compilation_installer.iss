; === Counterpick Installer Script ===
; Полностью готовая версия под твою структуру (release_stub находится на уровень выше)

#define MyAppName "Counterpick"
#define MyAppVersion "1.0"
#define MyAppPublisher "Capu"
#define MyAppURL "https://pokashto.net"
#define MyAppExeName "Counterpick.exe"

[Setup]
AppId={{A01D7350-2D1D-4993-9580-7C4C63520DFC}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={pf}\{#MyAppName}
DiskSpanning=yes
UninstallDisplayIcon={app}\{#MyAppExeName}
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=yes
OutputBaseFilename=Counterpick-Setup
SetupIconFile=..\release_stub\launcher_icon.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Копируем всё содержимое папки release_stub (на уровень выше)
Source: "..\release_stub\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Ярлык в меню Пуск
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\launcher_icon.ico"
; Ярлык на рабочем столе
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\launcher_icon.ico"; Tasks: desktopicon

[Run]
; Запуск лаунчера после установки
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Удаляем временные скриншоты при деинсталляции
Type: filesandordirs; Name: "{app}\tmp_screenshots"
