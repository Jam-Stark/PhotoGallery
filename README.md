# PhotoGallery

这是我的在线相册，内容来自 Google Drive 同步生成。

访问地址：

https://jam-stark.github.io/PhotoGallery/

> 提醒：由于图片资源依赖 Google 服务，部分网络环境可能无法直接访问，建议开启 VPN。
一个纯前端的照片画廊页面。为了避免在前端暴露 Google Drive API Key，仓库改为通过 GitHub Actions 周期性拉取 Drive 元数据并生成静态文件 `gallery-data.json`，前端只读取这个静态 JSON。