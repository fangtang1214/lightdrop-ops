# 轻放直播电商运营助手

面向直播电商复盘的本地桌面工具。当前版本先实现 MVP 闭环：扫描差品图片目录、用图片 dHash 做基础相似匹配、生成商品分组、查看最近 4 / 6 / 10 场重复差品，并导出 Excel。

## 技术栈

- 前端：React + TypeScript + Vite + Ant Design
- 桌面壳：Electron
- 后端：Python + FastAPI + Pillow + openpyxl

## 目录结构

```text
apps/
  desktop/     Electron 桌面端
  web/         React 前端
backend/       FastAPI 后端
data/          本地数据与缓存目录
docs/          开发文档
```

## 本地开发

最简单的启动方式：

双击项目根目录里的：

```text
启动轻放助手.vbs
```

备用启动方式：

如果双击后没有反应，可以双击：

```text
启动轻放助手.cmd
```

这个窗口会显示启动日志，方便排查问题。

如果异常退出后发现后台还有残留服务，可以双击：

```text
关闭残留服务.cmd
```

安装前端依赖：

```bash
npm install
```

安装后端依赖：

```bash
python -m pip install -r backend/requirements.txt
```

启动桌面 GUI：

```bash
npm run dev
```

GUI 窗口会自动启动后端服务和 Web 前端服务，并提供“打开 Web 前端”按钮。关闭 GUI 窗口时，由它启动的服务也会一起结束。

单独启动后端：

```bash
npm run dev:backend
```

单独启动前端：

```bash
npm run dev:web
```

## 图片目录格式

```text
差品图片库/
├── 2026-05-01_第1场/
│   ├── 商品A.jpg
│   └── 商品B.png
└── 2026-05-03_第2场/
    ├── 商品A_截图.jpg
    └── 商品C.webp
```

支持 `.jpg`、`.jpeg`、`.jfif`、`.png`、`.webp`、`.bmp`。
