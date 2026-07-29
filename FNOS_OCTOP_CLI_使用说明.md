# 飞牛（FnOS）本地版 OCTOP 命令行使用说明

OCTOP 本地版（native 包）安装后，**官方 `octop` 命令已自动注册到系统 PATH**，无需手动配置即可像官方发行版一样使用全部子命令。

---

## 一、装好后命令在哪、怎么用

安装包在「安装后回调」里把官方 CLI 包装脚本链接到了 PATH：

- `/usr/local/bin/octop` → 官方 CLI（推荐用这个）
- `/usr/local/bin/octop-cli` → 同上，别名

直接在飞牛终端（SSH 或应用中心的终端）使用：

```bash
# 查看全部子命令
octop --help

# 查看版本
octop version

# 查看已配置的模型供应商
octop provider list

# 查看智能体
octop agent list

# 查看用户
octop user list

# 查看/管理 IM 渠道、定时任务、技能、备份等
octop channel --help
octop cron --help
octop skills --help
octop backup --help
```

> 完整子命令：`acp / admin / agent / backup / channel / chats / clean / completion / config / cron / init / models / plugin / provider / run / service / skills / update / user / version`。

---

## 二、命令是怎么跑起来的（原理，方便排查）

`octop` 命令本质是调用包内 Python 3.12 运行 `python -m octop.cli.main <子命令>`，并自动设好：

| 环境变量 | 值 |
| --- | --- |
| `PYTHONPATH` | `/var/apps/octop-native/site-packages` |
| `OCTOP_HOME` | `<数据目录>/.octop` |
| `OCTOP_DATA_DIR` | `<数据目录>`（优先飞牛 data-share，否则 `/var/apps/octop-native/shares/octop-native/data`）|
| Python | 飞牛应用商店的 `/var/apps/python312/target/bin/python3.12` |

为避免产生 root 所有的数据文件（Web 服务以 `octop-native` 用户运行），CLI **以 `octop-native` 身份执行**：

- 以 root 运行 `octop`：通过 `sudo -u octop-native` 免密切换，无需输密码。
- 以普通用户运行 `octop`：同样尝试 `sudo -u octop-native`，需要输入该普通用户的 sudo 密码。

如果你在终端里想直接用绝对路径（不依赖 PATH 链接），也可以：

```bash
/var/apps/octop-native/bin/octop-cli --help
```

---

## 三、重要注意事项

1. **不要手动执行 `octop run`。**
   本机的 Web 服务由飞牛应用中心托管（`cmd/main` 拉起服务，监听 `0.0.0.0:8089`）。手动 `octop run` 会再起一个实例抢占 8089 端口，导致冲突。日常使用打开应用中心的「OCTOP」即可，无需手动起服务。

2. **Web 控制台才是主入口。**
   命令行主要用于运维/查看（如 `provider list`、`user list`、`backup`、`clean`）。配置模型、智能体、IM 渠道等建议在浏览器打开 `http://<设备IP>:8089` 的控制台完成。

3. **写类命令用对身份。**
   `octop init`、`octop user add` 等会改动数据目录文件。保持用 `octop`（默认切到 `octop-native`）执行，不要显式 `sudo octop ...` 以 root 去写，否则文件属主变成 root，服务（octop-native）后续可能没权限读。

---

## 四、安装前的端口自检（避免装完起不来）

安装包在「安装前」会自动清理 `8088` / `8089` 端口的残留进程：

- 先用 `ss -ltnp`（回退 `fuser` / `lsof`）按监听端口找出占用进程并 TERM → KILL；
- 再用 `pgrep -f 'octop.cli.main run'` 等命令行特征兜底清理（防止某些环境下拿不到 pid）；
- 本地版固定使用 **8089**，Docker 版使用 8088。

正常情况下你无需手动处理；若之前手动 `octop run` / 手动调试留下过孤儿进程，重装时会自动杀掉。如仍怀疑端口被占，可在飞牛终端确认：

```bash
ss -ltnp | grep -E ':8088|:8089'
# 或
fuser 8089/tcp
```

---

## 五、卸载时会清理什么

卸载（无论保留/删除数据）都会移除：

- `/etc/sudoers.d/octop-native`（免密 sudo 规则）
- `/usr/local/bin/octop` 与 `/usr/local/bin/octop-cli`（命令链接）
- 残留的虚拟桌面 systemd 单元（octop-desktop-*）

选择「完全删除」时还会清除 data-share 下的用户数据目录。

---

## 六、排错速查

| 现象 | 处理 |
| --- | --- |
| `octop` 命令找不到 | 重装一次；或直接使用 `/var/apps/octop-native/bin/octop-cli` |
| 提示 `未找到 Python 3.12` | 飞牛应用中心 → 开发工具 → 安装「Python 3.12」，再重装 |
| 远程桌面/浏览器安装报 `a password is required` | 飞牛终端(root) 执行 `visudo -c` 检查主 sudoers；重写 `/etc/sudoers.d/octop-native` 为 `octop-native ALL=(ALL) NOPASSWD: ALL` 并 `chmod 0440` |
| 服务起不来 / 端口被占 | 看上「安装前的端口自检」；必要时 `fuser -k 8089/tcp` 后重装 |
