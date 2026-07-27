# Octop — 飞牛 FnOS 安装包

本目录包含将 [TencentCloud/Octop](https://github.com/TencentCloud/Octop) 打包为飞牛 fnOS `.fpk` 安装包所需的全部文件，并附带自动同步上游 + 自动构建的 GitHub Actions。

## 目录结构

```
fnos/
├── manifest              # 应用元信息（名称/版本/端口/桌面入口等）
├── ICON.PNG / ICON_256.PNG
├── LICENSE               # 复用仓库根 LICENSE（MIT）
├── cmd/                  # 生命周期脚本（main / install_callback / config_callback 等）
├── config/
│   ├── privilege         # 权限声明（docker-octop 用户）
│   └── resource          # 资源声明（docker-project + 数据共享目录）
├── wizard/
│   ├── install           # 安装向导（可配置管理员账号/密码、日志级别、LLM 密钥）
│   ├── config            # 重新配置向导
│   ├── uninstall
│   └── upgrade
├── app/
│   ├── docker/
│   │   └── docker-compose.yaml   # 引用 ghcr.io/veenyi/octop:latest
│   └── ui/
│       ├── config                # 桌面图标入口
│       └── images/icon-{64,256}.png
└── Dockerfile            # 从仓库源码构建镜像，安装全部附加组件（browser + desktop）
```

## 工作机制

1. **源码同步**：`.github/workflows/zz-sync-upstream.yml` 每 6 小时把上游 `TencentCloud/Octop` 的更新合并进本仓 `main` 分支（使用仓库自带 `GITHUB_TOKEN`，无需 PAT）。
2. **镜像构建**：`.github/workflows/zz-build-fpk.yml` 的 `image` job 在 `main` 更新时，用 `fnos/Dockerfile` 从仓库源码构建 Octop 镜像并推送到 `ghcr.io/veenyi/octop:latest`（含全部附加组件）。
3. **安装包构建**：同一 workflow 的 `fpk` job 用 `scripts/build-fpk.sh` 把 `fnos/` 打成 `.fpk`，并以滚动发布 `fnos-latest` 提供下载。

## 本地构建 .fpk（无需 Docker）

```bash
bash scripts/build-fpk.sh
# 产物: dist/octop-<version>.fpk
```

`.fpk` 为「双层 gzip tar」：外层含 `app.tgz / cmd / config / wizard / ICON.PNG / ICON_256.PNG / LICENSE / manifest`，内层 `app.tgz` 含 `app/` 内容。

## 在飞牛上安装

1. 飞牛「应用中心 → 设置 → 手动安装应用」选择 `dist/octop-<version>.fpk`。
2. 安装向导中设置管理员账号/密码、日志级别、LLM 密钥（可选）。
3. 安装完成后桌面出现「Octop AI 助手」图标，浏览器打开 `http://<设备IP>:8088`。
4. 镜像首次会从 `ghcr.io/veenyi/octop:latest` 拉取；请确保该镜像为公开（workflow 已自动设为 public）。

> 服务端口固定为 `8088`（飞牛端口映射与桌面图标均据此）。附加组件（browser 浏览器自动化 + desktop 桌面控制）已在镜像中默认安装。
