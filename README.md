# PhotoGallery

一个纯前端的照片画廊页面。为了避免在前端暴露 Google Drive API Key，仓库改为通过 GitHub Actions 周期性拉取 Drive 元数据并生成静态文件 `gallery-data.json`，前端只读取这个静态 JSON。

## 工作流说明

- Workflow: `.github/workflows/refresh-gallery-data.yml`
- 触发方式：
  - 手动触发（`workflow_dispatch`）
  - 每 6 小时自动刷新一次（cron）
- 运行脚本：`scripts_generate_gallery_data.py`

## 需要配置的 GitHub Secrets

在仓库 `Settings -> Secrets and variables -> Actions` 中添加：

- `GDRIVE_API_KEY`: 仅服务端（Actions）使用的 Google Drive API Key
- `ROOT_FOLDER_ID`: 照片根目录的 Google Drive Folder ID

### Secrets 放置位置与命名（关键）

你问的“这个 API 放哪、怎么命名才能识别”，答案是：

1. 进入你的 GitHub 仓库页面（不是本地）。
2. 打开 `Settings` → `Secrets and variables` → `Actions`。
3. 点击 `New repository secret`，分别创建以下两个 Secret（名字必须完全一致，区分大小写）：
   - `GDRIVE_API_KEY`
   - `ROOT_FOLDER_ID`
4. 保存后去 `Actions` 页手动运行 `Refresh gallery data` workflow（`Run workflow`）。

之所以必须这样命名，是因为工作流里通过下面这两行读取它们：

```yml
GDRIVE_API_KEY: ${{ secrets.GDRIVE_API_KEY }}
ROOT_FOLDER_ID: ${{ secrets.ROOT_FOLDER_ID }}
```

如果 Secret 名称不一致（比如写成 `GOOGLE_API_KEY`），workflow 会读取不到，脚本会报缺少环境变量。

## 本地手动生成数据

```bash
GDRIVE_API_KEY=xxx ROOT_FOLDER_ID=xxx python scripts_generate_gallery_data.py
```

执行后会更新根目录下的 `gallery-data.json`。
