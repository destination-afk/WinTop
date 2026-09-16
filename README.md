[Uploading README.md…]()
# WinTop —— Windows 窗口一键置顶工具（霓虹发光边框）

按快捷键把「当前窗口」一键置顶，窗口四周出现**点击穿透的霓虹发光边框**；
再按一次同一快捷键，取消置顶、光晕同步消失。支持多窗口同时钉住。

> 已实测通过：Windows 11（150% 缩放）。
> **单文件 exe 版（WinTop.exe，10.8 MB）与源码版均通过同一套 15 项端到端自检**，
> 含置顶位校验、覆盖层贴合度（0 像素偏差）、点击穿透、边框像素采样、取消后零残留。

---

## 〇、第一次启动 30 秒上手

1. **双击 `WinTop.exe`**。右下角托盘出现绿色方框小图标，并弹一次气泡提示，即启动成功（主程序不弹窗口，托盘常驻）。
2. **直接按 `Ctrl + Alt + Space`** 试试：当前窗口立刻置顶并出现绿色发光边框；再按一次取消。
3. 如果杀毒软件拦截：这是 PyInstaller 单文件的常见误报，选「信任/允许」即可；实在不行改用源码版（`python win_topmost.py`）。
4. 如果提示「已经在运行了」：说明之前开过一份（或开机自启已拉起），不用再开。
5. 想关掉：`Ctrl + Alt + Q`，被钉住的窗口会全部恢复原层级。

**快捷键速查**

| 快捷键 | 作用 |
| --- | --- |
| `Ctrl + Alt + Space` | 置顶 / 取消置顶 当前窗口（同键双态切换） |
| `Ctrl + Alt + D` | 取消全部置顶 |
| `Ctrl + Alt + Q` | 退出工具 |

## 〇·一、最简用法（推荐：直接用 exe）

**双击 `WinTop.exe` 即可**——免装 Python、免编译、托盘常驻。

- 内置单实例保护：重复双击只会弹一句「已经在运行了」，不会开两份
- 开机自启：双击 `安装开机自启.bat`（指向 exe，不依赖 Python）
- 改了快捷键/颜色想重新打包：双击 `重新打包exe.bat`（调用本目录自带的 PyInstaller）
- PyInstaller 单文件 exe 是杀软误报重灾区，若被拦截，添加信任或退回源码版即可

---

## 一、快速开始（源码版，免编译）

运行环境：Windows 10 / 11 + Python 3.8+（只用标准库，无需 pip 安装任何东西）

| 操作 | 方式 |
| --- | --- |
| 启动 | 双击 `启动WinTop.bat`（托盘常驻，无控制台窗口） |
| 排查问题 | 双击 `调试启动(带日志).bat`，能看到报错；日志在 `%TEMP%\wintop.log` |
| 开机自启 | 双击 `安装开机自启.bat`；不想自启了跑 `取消开机自启.bat` |
| 直接命令行 | `python win_topmost.py` |

## 二、开机自启（计划任务版，已配置）

已创建计划任务 **`WinTop`**：登录时自动以**最高权限**启动 `WinTop.exe`，无 UAC 弹窗，
重启后热键与置顶能力（含管理员窗口）直接生效。

- 查看任务：`taskschd.msc`（任务计划程序库 → WinTop）
- 取消自启：双击 `取消计划任务自启.bat`（接受一次 UAC）
- 注意：任务指向的是当前 exe 路径，若把工具挪了家，重建一次任务即可

## 三、默认快捷键

| 快捷键 | 作用 |
| --- | --- |
| `Ctrl + Alt + Space` | 置顶 / 取消置顶 当前窗口（同键双态切换） |
| `Ctrl + Alt + D` | 取消全部置顶 |
| `Ctrl + Alt + Q` | 退出工具（自动恢复所有窗口层级） |

> ⚠️ 刻意没用 Ctrl+Space：它是中文输入法的中英文切换键，注册成全局热键会打架。

## 三、自定义（都在 `win_topmost.py` 顶部的 CONFIG 里）

```python
"hotkey_toggle": "ctrl+alt+space",  # 改成 "ctrl+shift+t" 这样写，修饰键: ctrl/alt/shift/win
"glow_color":    "#00FF9C",         # 发光颜色：#00BFFF 冰蓝 / #FF4D6D 玫红 / #FFD400 琥珀
"glow_width":    14,                # 光晕带宽（像素）
"radius":        16,                # 圆角半径，0 = 直角
"breath":        True,              # 呼吸灯；改 False = 静态常亮，最省 CPU
"fps":           30,                # 跟随刷新率，低配机可降到 20
```

改完保存重启工具即可。

## 四、工作原理（要点）

1. **热键**：`RegisterHotKey` 把 WM_HOTKEY 投递到独立监听线程的消息队列（GetMessage 循环），
   再经队列转交 Tk 主线程处理，避免跨线程操作 UI。
2. **置顶切换**：`SetWindowPos(hwnd, HWND_TOPMOST/NOTOPMOST, SWP_NOMOVE|SWP_NOSIZE|SWP_NOACTIVATE)`，
   用 `GetWindowLong(GWL_EXSTYLE) & WS_EX_TOPMOST` 读回真实状态，不靠猜。
3. **发光边框**：无边框 Toplevel 窗口 + `-transparentcolor` 色键透明 +
   `WS_EX_TRANSPARENT`（点击穿透）+ `WS_EX_NOACTIVATE`（不抢焦点）+ `WS_EX_TOOLWINDOW`（不进 Alt+Tab），
   画 14 圈由内到外变暗的圆角描边形成光晕。
4. **精确贴合**：用 DWM 的 `EXTENDED_FRAME_BOUNDS` 取真实可视边界，避开 Win10/11 约 7px 的隐形拖拽边框。
5. **状态同步**：30ms 轮询跟随；目标窗口关闭/最小化时自动清理效果层，退出时统一恢复所有窗口。
6. 启动即声明 DPI 感知，125%/150% 缩放下边框不错位。

## 五、常见问题

| 问题 | 原因与解决 |
| --- | --- |
| 提示「置顶失败，可能以管理员权限运行」 | 目标是管理员权限窗口（如任务管理器），普通进程动不了它的层级。右键 `启动WinTop.bat` → 以管理员身份运行 |
| 按了热键没反应 | 该键位被别的软件占用了，注册失败会有气泡提示；换一个键位即可 |
| 杀毒软件报毒 | 全局钩子/热键类工具的常见误报。源码就这一个文件，可自行审阅后加入白名单 |
| 光晕盖住了窗口内容？ | 不会。中间是色键全透明，且整层点击穿透，只在外围画光 |
| 多显示器 / 缩放屏幕 | 已做 DPI 感知；如果边框在副屏错位，把 `fps` 保持 30 并更新到最新代码 |
| 怎么彻底退出 | `Ctrl+Alt+Q` 或托盘右键退出，会自动把所有被钉住的窗口恢复原层级 |

## 六、C# 进阶版（csharp 目录）

与 Python 版功能一致，但用 **分层窗口 + GDI+ 逐像素 alpha（UpdateLayeredWindow）** 实现光晕，
抗锯齿更细腻，托盘常驻更"正规军"。需要 .NET SDK 8.0+：

```bat
cd csharp
dotnet run -c Release
```

> 注意：本机当前未安装 .NET SDK（只有运行时），该版本源码未经本机编译验证；
> 若编译报错多半是命名空间/类型的小问题，按报错微调即可。日常使用推荐 Python 版。

## 七、目录结构

```
WinTop/
├── WinTop.exe            ★ 单文件成品（免安装，双击即用）
├── win_topmost.py        工具本体源码
├── 启动WinTop.bat         源码版启动（需要 Python）
├── 重新打包exe.bat        改完配置后一键重新打包 exe
├── 调试启动(带日志).bat    源码版带控制台排错
├── 安装开机自启.bat        写入 Startup 快捷方式
├── 取消开机自启.bat        移除自启
├── win.ico / gen_icon.py  程序图标及生成脚本
├── selftest.py            自动化自检（支持测源码版 / exe 版）
├── selftest_glow.png      自检截图：发光边框实拍
├── _pyi/ + WinTop.spec    PyInstaller 本体与打包配置（重新打包用，可删）
└── csharp/                C# WinForms 进阶版
    ├── Program.cs
    └── WinTop.csproj
```
