# Quick App Launcher

由原本的 Riot Launcher 概念改成通用 Windows 應用程式啟動器。

## 功能

- 圖形介面新增、編輯、刪除及排序應用程式
- 每個項目可設定：
  - 執行檔路徑
  - 命令列參數
  - 工作目錄
  - 啟動前延遲
  - 是否啟用
  - 是否納入自動啟動模式
  - 避免重複啟動
- 支援 `%LOCALAPPDATA%`、`%APPDATA%`、`%PROGRAMFILES%` 等環境變數
- `--startup` 無介面模式，適合搭配 Windows 工作排程器
- 使用 Queue 將背景執行緒訊息安全地送回 Tkinter UI
- 設定檔 UTF-8 與原子寫入，降低設定檔損壞機率
- 不再依賴 Riot Client 私有 API

## 執行

需要 Python 3.10 以上，不需要額外套件。

```powershell
python main.py
```

第一次執行會建立空白 `appsettings.json`。  
也可將 `appsettings.example.json` 複製成 `appsettings.json` 後修改路徑。

## 工作排程器建議

程式本身已支援初始等待，因此排程器不用再設定延遲，避免重複等待。

1. 觸發程序：使用者登入時
2. 動作：
   - Python 版程式：`pythonw.exe`
   - 引數：`"完整路徑\main.py" --startup`
   - 起始位置：專案資料夾
3. 若已打包成 exe：
   - 程式：`QuickAppLauncher.exe`
   - 引數：`--startup`
4. 不要勾選「使用最高權限執行」，除非某個 App 確實需要管理員權限。

## 打包 exe

```powershell
py -m pip install pyinstaller
pyinstaller --noconfirm --onefile --windowed --name QuickAppLauncher main.py
```

產物位於：

```text
dist\QuickAppLauncher.exe
```

將 exe 與 `appsettings.json` 放在同一資料夾。

## Riot Client

Riot 可以視為一般應用程式設定，例如：

```json
{
  "name": "Riot Client",
  "path": "C:\\Riot Games\\Riot Client\\RiotClientServices.exe",
  "arguments": "--launch-product=league_of_legends --launch-patchline=live",
  "working_directory": "C:\\Riot Games\\Riot Client",
  "delay_seconds": 0,
  "enabled": true,
  "startup_enabled": false,
  "prevent_duplicate": true
}
```

這樣不需要讀取 Riot lockfile，也不會因 Riot 私有 API 改版而讓整個啟動器失效。

## 建議設定

- LINE：0 秒，自動啟動
- Telegram：5 秒，自動啟動
- Brave：30 秒，自動啟動
- VS Code：60 秒，視需求決定
- Riot / Blitz / Beanfun：不要自動啟動；在需要玩遊戲時由 UI 一次選取啟動
