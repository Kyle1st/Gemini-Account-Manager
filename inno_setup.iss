; ═══════════════════════════════════════════════════════════════
;  Gemini Account Manager - Inno Setup 安装包配置
;  使用方法:
;    1. 先运行 build.bat 完成 PyInstaller 打包
;    2. 下载安装 Inno Setup: https://jrsoftware.org/isdl.php
;    3. 用 Inno Setup 打开本文件，点击编译即可生成安装包
; ═══════════════════════════════════════════════════════════════

#define MyAppName "Gemini Account Manager"
#define MyAppVersion "1.2"
#define MyAppPublisher "Gemini Account Manager"
#define MyAppExeName "GeminiAccountManager.exe"
#define MyAppSourceDir "dist\GeminiAccountManager"

[Setup]
AppId={{A7E3F2D1-B8C4-4E5F-9A6D-0C1B2E3F4A5B}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=installer_output
OutputBaseFilename=GeminiAccountManager_Setup_v{#MyAppVersion}
; 使用 LZMA2 极限压缩
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes
; UI 设置
WizardStyle=modern
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
SetupLogging=no
; 取消注释下面这行并指定 .ico 文件路径来自定义安装包图标
; SetupIconFile=app.ico
; UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce

[Files]
; 将 PyInstaller 输出目录下的所有文件都打入安装包
Source: "{#MyAppSourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\卸载 {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "启动 {#MyAppName}"; Flags: nowait postinstall skipifsilent
