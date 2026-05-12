#define MyAppName "求职助手"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "Job Search Assistant"
#define MyAppExeName "job-search-assistant.exe"

[Setup]
AppId={{7A2E32B5-8C6E-4D47-9E38-61A26D06A8D4}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\JobSearchAssistant
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\..\dist
OutputBaseFilename=JobSearchAssistantSetup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64

[Languages]
Name: "chinesesimp"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加任务"; Flags: checkedonce

[Files]
Source: "..\..\dist\JobSearchAssistant\job-search-assistant\*"; DestDir: "{app}\job-search-assistant"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\..\dist\JobSearchAssistant\extension\*"; DestDir: "{app}\extension"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\..\dist\JobSearchAssistant\docs\*"; DestDir: "{app}\docs"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\..\dist\JobSearchAssistant\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\dist\JobSearchAssistant\config.yaml"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\job-search-assistant\{#MyAppExeName}"
Name: "{group}\扩展目录"; Filename: "{app}\extension"
Name: "{group}\使用说明"; Filename: "{app}\README.md"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\job-search-assistant\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\job-search-assistant\{#MyAppExeName}"; Description: "启动求职助手"; Flags: nowait postinstall skipifsilent
