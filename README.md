# 轻放直播电商运营助手

> LightDrop LiveOps Assistant — 直播电商数据分析与运营复盘工具

面向直播电商运营人员的桌面端工具，帮助快速筛查重复差品、分析优品、对比转化落差、复盘直播大屏数据、转写音视频。

## 功能概览

| 模块 | 说明 |
|------|------|
| **差品分析** | 扫描差品图片目录，通过图片相似度匹配找出跨场次重复出现的差品商品 |
| **优品分析** | 基于直播数据表格，按转化率、成交数等指标综合排名，筛选优质商品 |
| **转化落差** | 对比当前场次与历史最佳表现，定位转化率下滑严重的商品 |
| **直播数据** | 单场直播全商品排名，含转化率、成交数、曝光、退款率等完整数据 |
| **大屏复盘** | OCR 识别直播大屏截图，生成分钟级指标曲线（推荐增量、点赞率、成交转化率等） |
| **视频转文字** | 上传音视频文件，自动转写为带时间戳和说话人的文字稿，支持导出 TXT/SRT/MD |

## 快速开始（使用者）

### 环境要求

- Windows 10/11
- Node.js 18+（[下载](https://nodejs.org/)）
- Python 3.10+（[下载](https://www.python.org/)）

### 安装依赖

```bash
# 前端依赖
npm install

# 后端依赖
python -m pip install -r backend/requirements.txt
```

### 启动程序

双击项目根目录中的 **`启动轻放助手.vbs`** 即可启动桌面程序。

程序会自动拉起后端服务和 Web 前端，在启动窗口中点击"打开 Web 前端"即可使用。

如果双击无反应，可改用 `启动轻放助手.cmd`（会显示启动日志，方便排查问题）。

如果异常退出后发现端口被占用，双击 `关闭残留服务.cmd` 清理残留进程。

### 图片目录格式

差品图片按场次分文件夹存放：

```text
差品图片库/
├── 2026-05-01_第1场/
│   ├── 商品A.jpg
│   └── 商品B.png
├── 2026-05-03_第2场/
│   ├── 商品A_截图.jpg
│   └── 商品C.webp
```

支持格式：`.jpg`、`.jpeg`、`.jfif`、`.png`、`.webp`、`.bmp`

### 视频转文字配置

使用"视频转文字"功能需要配置阿里云百炼 API Key，详见 [视频转文字配置文档](docs/transcripts.md)。

## 开发指南（开发者）

### 项目结构

```text
lightdrop-ops/
├── apps/
│   ├── desktop/          Electron 桌面端（主进程、启动器）
│   └── web/              React 前端（Vite + TypeScript + Ant Design）
│       └── src/
│           ├── app/      应用壳（布局、导航、命令栏）
│           ├── features/ 功能页面（差品、优品、转化落差、大屏复盘、转写、服务状态）
│           ├── hooks/    自定义 Hooks
│           ├── shared/   共享组件与工具
│           └── api/      API 客户端与类型定义
├── backend/              FastAPI 后端（Python）
│   └── app/
│       ├── api/          路由
│       ├── services/     业务逻辑（扫描、匹配、报告、转写等）
│       └── models/       数据模型
├── data/                 本地数据目录（缓存、转写文件，不入库）
└── docs/                 文档
```

### 技术栈

| 层 | 技术 |
|----|------|
| 前端 | React 18 + TypeScript + Vite + Ant Design 5 + Lucide Icons |
| 桌面端 | Electron |
| 后端 | Python + FastAPI + Pillow + openpyxl |
| 图片匹配 | dHash 感知哈希 |

### 开发命令

```bash
# 启动完整桌面端（Electron + 后端 + 前端）
npm run dev

# 仅启动 Web 前端（端口 5173）
npm run dev:web

# 仅启动后端（端口 8000，热重载）
npm run dev:backend

# 构建前端产物
npm run build
```

### 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `LIGHTDROP_BACKEND_URL` | 后端地址 | `http://127.0.0.1:8000` |
| `LIGHTDROP_WEB_URL` | 前端地址 | `http://127.0.0.1:5173` |
| `LIGHTDROP_BACKEND_HOST` | 后端绑定地址 | `0.0.0.0` |
| `LIGHTDROP_WEB_HOST` | 前端绑定地址 | `0.0.0.0` |

更多开发细节请参阅 [开发文档](docs/development.md)。

## 许可

私有项目，未公开授权。
