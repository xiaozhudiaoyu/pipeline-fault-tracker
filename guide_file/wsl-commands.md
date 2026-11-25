# WSL 完整命令文档（命令参考手册）

> 定位：**命令参考手册**——按命令条目组织，供速查与复制。教程式流程（概念讲解、完整部署步骤、坑点详解）见 [wsl.md](wsl.md)，两文档分工不重复。
> 实测基线：WSL **2.7.14.0** / 内核 **6.18.33.2-2** / Ubuntu **26.04.1 LTS** / Windows **10.0.19045**（2026-09-22 实测）。
> 可信度标注：「实测」= 本机执行验证过的命令与输出；其余为 `wsl --help` / 官方文档内容。命令示例统一避开中文路径（中文路径坑见 [wsl.md](wsl.md) 3.5 节）。
> 执行位置约定：**PowerShell** = Windows 终端；**bash** = WSL 内。

---

## 目录

1. [wsl.exe 命令全集](#一wslexe-命令全集powershell)
2. [配置文件](#二配置文件)
3. [Windows ↔ WSL 互操作命令](#三windows--wsl-互操作命令)
4. [WSL 内 Linux 常用命令](#四wsl-内-linux-常用命令bash)
5. [本项目命令速查（D5）](#五本项目命令速查d5)
6. [坑点速查](#六坑点速查)

---

## 一、wsl.exe 命令全集（PowerShell）

> 来源：本机 `wsl --help` 实测（WSL 2.7.14.0 的全部选项）。语法 `wsl.exe [Argument] [Options...] [CommandLine]`。

### 1.1 运行 Linux 命令

```powershell
wsl                          # 无参数：进入默认发行版的交互式 shell
wsl [命令]                   # 直接执行 Linux 命令（结果回到 PowerShell）
wsl --exec, -e <CommandLine> # 不启动 shell，直接执行命令（推荐脚本用）
wsl --shell-type <standard|login|none>   # 指定 shell 类型
wsl --                       # 终止选项解析：其后全部内容按命令传给 Linux
```

运行选项：

| 选项 | 说明 |
|---|---|
| `--cd <Directory>` | 指定起始目录。`~` 用 Linux 主目录；`/` 开头的绝对路径按 Linux 路径处理；其余按 Windows 路径转换 |
| `--distribution, -d <DistroName>` | 指定发行版 |
| `--distribution-id <DistroGuid>` | 按发行版 GUID 指定（`--list --verbose` 可查） |
| `--user, -u <UserName>` | 以指定用户运行（`-u root` 免 sudo 密码，装软件常用） |
| `--system` | 为 systemd 启动发行版 shell（本机已开 systemd，见 2.2） |

示例（实测）：

```powershell
wsl -e bash -c 'whoami'                  # 免进交互 shell 跑一条命令
wsl -u root -e bash -c 'apt-get update'  # root 身份执行（无交互密码）
wsl -d Ubuntu                            # 指定发行版进入
```

### 1.2 查询类

```powershell
wsl --help                        # 帮助（全部选项）
wsl --version, -v                 # 版本信息（WSL / 内核 / WSLg 各组件）
wsl --status                      # 默认版本、内核版本、默认发行版
wsl --list, -l [选项]             # 列出发行版
wsl --list --verbose, -l -v       # 详细：名称 / 状态 / 版本（最常用）
wsl --list --running              # 只列运行中的发行版
wsl --list --quiet, -q            # 只输出名称（脚本取用）
wsl --list --all                  # 含正在安装/注销中的发行版
wsl --list --online, -o           # 列出可在线安装的发行版
```

实测输出：

```
$ wsl --list --verbose
  NAME      STATE           VERSION
* Ubuntu    Stopped         2

$ wsl --version
WSL 版本: 2.7.14.0
内核版本: 6.18.33.2-2
WSLg 版本: 1.0.73.2
Windows: 10.0.19045.6466
```

### 1.3 安装与更新

```powershell
wsl --install [发行版名] [选项]     # 安装 WSL 本体 + 发行版
wsl --install                        # 装 WSL 2 + 默认发行版 Ubuntu
wsl --install -d Ubuntu              # 指定发行版
wsl --update                         # 更新 WSL 内核与本体（--pre-release 用预览版）
wsl --uninstall                      # 彻底卸载 WSL（各发行版需先 --unregister）
```

`--install` 的选项（2.7.x 新增较多）：

| 选项 | 说明 |
|---|---|
| `--no-distribution` | 只装 WSL 本体，不装发行版 |
| `--no-launch, -n` | 安装后不自动启动 |
| `--web-download` | 从网络直接下载（不用 Microsoft Store） |
| `--location <Location>` | 指定安装位置（默认 C 盘） |
| `--name <Name>` | 自定义发行版名称 |
| `--version <Version>` | 指定 WSL 版本（1/2） |
| `--enable-wsl1` | 同时启用 WSL1 支持 |
| `--vhd-size <MemoryString>` | 预分配 VHD 大小（如 `32GB`） |
| `--from-file <Path>` | 从本地 tar/Appx 文件安装 |
| `--legacy` | 传统发行版安装方式 |

### 1.4 发行版生命周期

```powershell
wsl --set-default, -s <发行版>            # 设默认发行版（裸 wsl 进入哪个）
wsl --set-version <发行版> <1|2>          # 转换发行版版本（WSL1↔WSL2）
wsl --terminate, -t <发行版>              # 停止指定发行版（不删数据）
wsl --shutdown                            # 停止所有发行版 + 关闭 WSL2 VM（释放内存）
wsl --shutdown --force                    # 强制关闭（有运行中操作也停，可能丢数据）
wsl --unregister <发行版>                 # 注销发行版并【删除其文件系统】（不可恢复！）
wsl --set-default-version <1|2>           # 新装发行版的默认版本
```

`--manage` 子命令（发行版设置，2.7.x）：

```powershell
wsl --manage Ubuntu --move <新位置>            # 移动发行版（如挪到 D 盘）
wsl --manage Ubuntu --set-sparse true           # VHD 稀疏模式：允许回收磁盘空间
wsl --manage Ubuntu --set-default-user <用户名> # 改默认用户（等价 wsl.conf 的 [user]）
wsl --manage Ubuntu --resize <MemoryString>     # 调整 VHD 大小（如 64GB）
```

### 1.5 备份与迁移

```powershell
wsl --export <发行版> <文件名> [选项]   # 导出为 tar（文件名 - 输出到 stdout）
wsl --export Ubuntu D:\ubuntu-backup.tar
wsl --export Ubuntu - --format tar.gz > backup.tar.gz   # 压缩导出

wsl --import <名称> <安装位置> <文件名> [选项]  # 从 tar 导入
wsl --import Ubuntu2 D:\wsl\ubuntu2 D:\ubuntu-backup.tar
wsl --import Ubuntu2 D:\wsl\ubuntu2 - --version 2     # 文件名 - 从 stdin

wsl --import-in-place <名称> <文件名>   # 直接挂载 .vhdx（ext4 格式），不复制
```

`--export` 选项：`--format <tar|tar.gz|tar.xz|vhd>`（默认 tar）。
`--import` 选项：`--version <1|2>`、`--vhd`（源是 vhd 而非 tar）。

**注意**：`--import` 出来的发行版默认以 **root** 登录且不含 `wsl.conf`，需手动配默认用户（见 2.2）。

### 1.6 物理磁盘挂载（进阶）

```powershell
wsl --mount <Disk>        # 把物理磁盘挂进 WSL2（Disk 为 \\.\PHYSICALDRIVE2 等）
wsl --mount <Disk> --vhd <路径.vhdx>          # 挂载 vhdx 文件
wsl --mount <Disk> --bare                    # 不自动挂分区（手动 mount）
wsl --mount <Disk> --partition <索引>         # 只挂指定分区
wsl --mount <Disk> --type <ext4|btrfs>       # 文件系统类型（未指定默认 ext4）
wsl --mount <Disk> --name <挂载点名称>        # 挂载点路径（/mnt/wsl/<name>）
wsl --unmount [Disk]                         # 卸载全部（或指定盘）
```

---

## 二、配置文件

### 2.1 `.wslconfig`（Windows 侧，全局 VM 设置）

路径：`C:\Users\<用户名>\.wslconfig`（本机**未创建**，全部用默认值；创建后 `wsl --shutdown` 生效）。

```ini
[wsl2]
memory=4GB                  # WSL2 VM 内存上限（默认 50% 物理内存）
processors=2                # CPU 核心数上限
swap=2GB                    # 交换空间（0 = 关闭）
swapFile=D:\\wsl\\swap.vhdx # 交换文件位置
localhostForwarding=true    # 端口转发（本项目依赖，勿关）
nestedVirtualization=true   # 嵌套虚拟化（跑 Docker 需要）
networkingMode=NAT          # NAT | mirrored（镜像网络模式）

[experimental]
autoMemoryReclaim=gradual   # 自动回收内存（gradual | dropcache）
sparseVhd=true              # VHD 稀疏模式
```

### 2.2 `wsl.conf`（Linux 侧，每发行版设置）

路径：`/etc/wsl.conf`。本机实测内容：

```ini
[boot]
systemd=true            # 启动 systemd（跑服务、Docker 需要）

[user]
default=xiaozhu         # 默认登录用户
```

全部可用段落：

```ini
[boot]
systemd=true            # 启用 systemd（WSL 0.67.6+）

[network]
hostname=devbox         # 自定义主机名
generateHosts=true      # 是否自动生成 /etc/hosts

[interop]
enabled=true            # 是否允许互操作（调 Windows 程序）
appendWindowsPath=true  # Windows PATH 是否追加到 Linux PATH（坑点见 wsl.md 第五节）

[user]
default=xiaozhu         # 默认用户

[automount]
enabled=true            # 是否自动挂载 Windows 盘到 /mnt
root=/mnt/              # 挂载根路径
options="metadata,umask=22"   # metadata 支持 Linux 权限位；umask 控制可见权限
```

修改后 `wsl --terminate Ubuntu` 重启生效（不丢数据，只是重启发行版）。

---

## 三、Windows ↔ WSL 互操作命令

### 3.1 `wslpath` 路径转换（实测）

```bash
wslpath -w <Linux路径>    # Linux → Windows 路径
wslpath -u <Windows路径>  # Windows → Linux 路径（/mnt/... 形式）
wslpath -m <路径>         # 输出混合形式（/ 分隔，可给 Windows 程序用）
wslpath -a <相对路径>     # 转绝对路径
```

实测输出：

```bash
$ wslpath -w /home/xiaozhu
\\wsl.localhost\Ubuntu\home\xiaozhu

$ wslpath -u "E:/pythonlearn"
/mnt/e/pythonlearn
```

**用途**：给 Windows 程序传 WSL 内路径（如 `explorer.exe "$(wslpath -w ~/project)"`）。注意含中文的 Windows 路径经 PowerShell 传参有编码坑（[wsl.md](wsl.md) 3.5 节），在 bash 内调用 `wslpath` 则无此问题。

### 3.2 从 WSL 调 Windows 程序

```bash
explorer.exe .          # 用资源管理器打开当前 WSL 目录
code .                  # VS Code 打开当前目录（需装 Remote-WSL 扩展）
clip.exe                # 把 stdin 复制进 Windows 剪贴板：echo hello | clip.exe
cmd.exe /c "dir"        # 执行 cmd 命令
powershell.exe -c "Get-Date"   # 执行 PowerShell 命令
ipconfig.exe            # 查 Windows 侧 IP
```

### 3.3 从 Windows 访问 WSL 文件

```powershell
explorer \\wsl$\Ubuntu\home\xiaozhu           # 资源管理器浏览 WSL 家目录
explorer \\wsl.localhost\Ubuntu\home\xiaozhu  # 等价写法
```

### 3.4 `WSLENV` 环境变量（跨系统共享变量）

```powershell
$env:WSLENV = "MY_VAR/p"   # /p 路径转换；/u Unix→Win；/w Win→Unix
$env:MY_VAR = "C:\temp"
wsl echo $MY_VAR           # WSL 内可见
```

---

## 四、WSL 内 Linux 常用命令（bash）

> 仅列本项目开发场景高频用法。`htop` 本机未预装（`sudo apt install htop` 可用），`top`/`ps` 已内置。

### 4.1 文件与目录

```bash
ls -la                 # 含隐藏文件 + 详细权限（实测）
pwd                    # 当前目录
cd ~ / cd -            # 回家目录 / 回上一目录
mkdir -p a/b/c         # 递归建目录
cp -r src dst          # 递归复制
mv a b                 # 移动/改名
rm file; rm -r dir     # 删文件 / 递归删目录（无回收站，谨慎）
find . -name "*.py"    # 按名查找
du -sh dir             # 目录大小（实测：du -sh ~/pipeline-fault-tracker → 2.4M）
df -h /home            # 磁盘空间（实测）
rsync -a --no-perms --no-owner --no-group --exclude=X ./ ~/dst/   # 跨系统复制（本项目部署实测）
tar -czf a.tar.gz dir  # 压缩打包
```

### 4.2 查看与编辑

```bash
cat file               # 全文输出
head -20 file / tail -5 file   # 头/尾 N 行
grep -i "keyword" file         # 忽略大小写搜索
grep -E 'a|b' file             # 扩展正则
less file              # 分页浏览（q 退出）
nano file              # 终端编辑器（已预装；Ctrl+X 退出、Ctrl+O 保存）
```

### 4.3 进程管理

```bash
ps aux                       # 全部进程（第 2 列即 PID，实测）
ps aux | grep uvicorn | grep -v grep   # 过滤进程（管道组合）
pgrep -f uvicorn             # 按命令行匹配 PID（已预装）
top                          # 实时监控（q 退出）
kill <PID>                   # 发 SIGTERM（15）优雅终止
kill -9 <PID>                # SIGKILL 强杀（不给进程清理机会，慎用）
kill -STOP <PID> / kill -CONT <PID>     # 暂停 / 恢复
pkill -f "vite"              # 按名字批量终止
jobs; fg %1                  # 查看 / 切回后台任务（Ctrl+Z 挂起）
nohup cmd > log 2>&1 &       # 后台运行、输出重定向（关终端不中断）
```

常用信号（本机 `kill -l` 实测）：`1 SIGHUP`、`2 SIGINT`（Ctrl+C）、`9 SIGKILL`、`15 SIGTERM`（默认）、`19 SIGSTOP`。

### 4.4 网络验证

```bash
curl -s http://127.0.0.1:8000/api/faults   # 请求接口（实测）
curl -s -o /dev/null -w "%{http_code}\n" URL   # 只看状态码
ss -tlnp                   # 监听中的 TCP 端口（已预装；-u 看 UDP）
ping -c 3 8.8.8.8          # 连通性（-c 限次数）
ip -4 addr show eth0       # WSL 侧 IP（Windows 关 localhostForwarding 时用）
```

### 4.5 软件安装

```bash
sudo apt update                     # 刷新包索引
sudo apt install -y nodejs npm      # 装包（-y 免确认）
apt-cache search <关键词>           # 搜索包
sudo apt remove <包名>              # 卸载（保留配置）
sudo apt purge <包名>               # 卸载 + 删配置
sudo apt list --installed | grep node   # 查已装
```

免交互技巧：从 PowerShell 用 `wsl -u root -e bash -c 'apt-get install -y ...'`（实测，本项目装 Node 用此法）。

### 4.6 文本流处理

```bash
# sed —— 流编辑器
sed 's/old/new/g' file             # 全局替换（每行所有匹配）
sed 's/old/new/' file              # 每行只替换第一个匹配
sed -i 's/old/new/g' file          # 直接修改文件（原地替换）
sed -i.bak 's/old/new/g' file     # 替换并备份原文件为 file.bak
sed -n '5,10p' file                # 只输出第 5~10 行
sed '3d' file                      # 删除第 3 行
sed '/pattern/d' file              # 删除匹配行
sed '$d' file                      # 删除最后一行
sed '2i\new line text' file        # 在第 2 行前插入
sed -e 's/a/b/g' -e 's/c/d/g' file   # 多条规则同时执行

# awk —— 模式扫描与处理
awk '{print $1}' file                  # 输出第一列（默认空白分隔）
awk -F: '{print $1}' /etc/passwd      # 自定义分隔符
awk '{sum += $1} END {print sum}' file   # 求和
awk '/pattern/ {print NR, $0}' file   # 匹配行带行号输出
awk 'NR==5,NR==10' file               # 输出第 5~10 行（等价 sed -n）
awk '{print NF}' file                  # 每行列数

# cut —— 按列截取
cut -d':' -f1 /etc/passwd       # 以 : 分隔取第 1 列
cut -d' ' -f1,3 file            # 取第 1、3 列
cut -c1-10 file                 # 取每行第 1~10 个字符

# tr —— 字符转换
tr 'a-z' 'A-Z' < file          # 小写转大写
tr -d '\r' < file               # 删除 Windows 回车符（CRLF → LF）
tr -s ' ' < file                # 压缩连续空格为单个
tr ',' '\t' < file              # 逗号替换为 Tab

# sort —— 排序
sort file                       # 按字典序排序
sort -r file                    # 逆序
sort -n file                    # 数值排序
sort -k2 -t: file               # 按第 2 列排序（-t 指定分隔符）
sort -u file                    # 去重后排序

# uniq —— 去重与统计（须先排序）
sort file | uniq -c             # 计数（每行出现次数）
sort file | uniq -d             # 只输出重复行
sort file | uniq -u             # 只输出不重复行

# wc —— 统计
wc -l file                     # 行数
wc -w file                     # 单词数
wc -c file                     # 字节数

# xargs —— 把 stdin 转为命令参数
find . -name '*.log' | xargs rm           # 批量删除
find . -name '*.py' | xargs grep 'import'  # 对查找结果执行搜索
echo "a b c" | xargs -n1 echo             # 每行一个参数
```

### 4.7 系统信息

```bash
uname -a                       # 全部系统信息（内核名/版本/架构等）
uname -r                       # 内核版本号（实测：6.18.33.2-2）
hostname                       # 主机名
uptime                         # 运行时间与负载均值
free -h                        # 内存使用（人类可读）
lscpu                          # CPU 架构信息
lsblk                          # 块设备（磁盘分区）
lsusb                          # USB 设备
dmesg | tail                   # 内核消息（最后 10 行）
lsof -i :8000                 # 查看谁占用 8000 端口（需安装）
```

### 4.8 日期与时间

```bash
date                           # 当前日期时间
date +%Y-%m-%d                 # 格式化输出（如 2026-09-23）
date +%s                       # Unix 时间戳
date -d @1727000000            # 时间戳转日期
cal                            # 本月日历
cal 2026                       # 全年日历
time command                   # 测量命令执行耗时
sleep 5                        # 暂停 5 秒（脚本延迟用）
touch file                     # 更新时间戳（文件不存在则创建空文件）
```

### 4.9 用户与组管理

```bash
sudo useradd -m newuser        # 新建用户（-m 自动建家目录）
sudo userdel -r newuser        # 删除用户（-r 连同家目录）
passwd username                # 改密码（当前用户直接 passwd）
su - username                  # 切换用户（- 加载目标用户环境）
groups username                # 查看用户所属组
sudo usermod -aG docker $USER  # 把当前用户加入 docker 组（Docker 常用）
last                           # 用户登录历史
w                              # 当前在线用户
id username                    # 指定用户的 UID / GID / 所属组
```

### 4.10 归档与压缩

```bash
# zip / unzip
zip -r archive.zip dir/        # 递归压缩目录
unzip archive.zip              # 解压到当前目录
unzip -l archive.zip           # 列出压缩包内容（不解压）

# gzip / gunzip（单文件压缩）
gzip file                      # 压缩为 file.gz（原文件被替换）
gunzip file.gz                 # 解压（.gz 被替换为原文件）
gzip -k file                   # 压缩并保留原文件（-k keep）

# bzip2 / xz（更高压缩率）
bzip2 file / bunzip2 file.bz2  # bzip2 压缩/解压
xz file / unxz file.xz         # xz 压缩/解压（压缩率最高但最慢）
```

### 4.11 文件对比

```bash
diff file1 file2               # 逐行对比（输出差异行）
diff -u file1 file2            # unified 格式（git diff 同款）
diff -r dir1 dir2              # 递归对比两个目录
diff -q file1 file2            # 只报告是否不同（不显示细节）
colordiff file1 file2          # 彩色差异（需安装 colordiff）
```

### 4.12 环境变量

```bash
env                            # 列出全部环境变量
printenv HOME                  # 查看单个变量值
echo $PATH                     # 查看 PATH
export MY_VAR="value"          # 设置并导出（当前 shell 及子进程可见）
unset MY_VAR                   # 删除变量
MY_VAR=hello command           # 仅给该命令临时设环境变量
source ~/.bashrc               # 重新加载配置（等价 `. ~/.bashrc`）
```

### 4.13 链接与特殊文件

```bash
ln -s target link              # 创建软链接（类似快捷方式）
ln target link                 # 创建硬链接（共享 inode）
readlink -f link               # 解析软链接的最终目标路径
mkfifo mypipe                  # 创建命名管道（进程间通信用）
mktemp                         # 创建临时文件（自动唯一命名）
mktemp -d                      # 创建临时目录
```

### 4.14 用户与权限

```bash
whoami / id            # 当前用户 / 用户组详情（实测：whoami → xiaozhu）
sudo <命令>            # 提权执行（首次要密码；用 -u root 可绕开）
chmod +x script.sh     # 加执行权限
chmod 755 file         # 数字权限（rwxr-xr-x）
chown user:group file  # 改属主
```

---

## 五、本项目命令速查（D5）

> 完整部署步骤与坑点见 [wsl.md](wsl.md) 第六节，此处一页速查。

| 场景 | 命令（PowerShell / bash 标注） |
|---|---|
| 检查 WSL | `wsl --list --verbose`（PowerShell，实测） |
| 复制项目进 WSL | 先 `cd` 项目根，再 `wsl -e bash -c 'mkdir -p ~/pipeline-fault-tracker && rsync -a --no-perms --no-owner --no-group --exclude=node_modules --exclude=.venv --exclude=dist --exclude=__pycache__ --exclude=.idea ./ ~/pipeline-fault-tracker/'`（实测 2.4M） |
| 装 Node | `wsl -u root -e bash -c 'apt-get update -qq && apt-get install -y -qq nodejs npm'`（实测 v22.22.1 / npm 9.2.0） |
| backend 依赖 | `cd ~/pipeline-fault-tracker/backend && uv sync`（bash） |
| frontend 依赖 | `cd ~/pipeline-fault-tracker/frontend && npm ci`（bash，实测 75 packages） |
| 起 backend | `cd ~/pipeline-fault-tracker/backend && uv run uvicorn app.main:app --reload`（bash，8000 端口） |
| 验 backend | `curl -s http://127.0.0.1:8000/api/faults`（bash） |
| 起 frontend | `cd ~/pipeline-fault-tracker/frontend && npm run dev`（bash，5173 端口，勿变） |
| 验 frontend | `curl -s http://127.0.0.1:5173/`（bash） |
| Windows 侧验证 | `curl.exe -s http://localhost:8000/api/faults`（PowerShell，注意是 curl.exe） |
| 查进程 | `ps aux | grep -E 'uvicorn|vite' | grep -v grep`（bash，实测 PID 990/993/1039/1040） |
| 停进程 | `kill 990; kill 1040`（bash） |
| 重建环境 | `rm -rf ~/pipeline-fault-tracker` 后重走复制→装依赖→启动（bash） |

---

## 六、坑点速查

> 详细机理见 [wsl.md](wsl.md) 第七节，此处一句话索引。

| # | 坑 | 规避 |
|---|---|---|
| 1 | PowerShell 传中文路径给 wsl.exe 乱码 | 先 `cd` 再启动 wsl，命令里只用相对路径 |
| 2 | `node: command not found` 但 npm 有输出 | appendWindowsPath 污染，apt 装 Linux 版 Node |
| 3 | Windows 的 node_modules/.venv 在 WSL 不可用 | 复制时排除，进 WSL 重装 |
| 4 | 5173 被占 vite 退避 → CORS 拦截 | 先释放 5173，白名单见 backend/app/config.py |
| 5 | PowerShell 裸 `curl` 是别名 | 一律 `curl.exe` |
| 6 | `/mnt/e` 下 npm install 慢且易错 | 项目放 ext4 家目录 |
| 7 | `--unregister` / `rm -rf` 不可逆 | 删前先 `--export` 备份 |
