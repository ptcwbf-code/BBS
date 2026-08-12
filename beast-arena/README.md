# 巨兽之战 · Beast Arena

跨越时空的顶级掠食者对决 —— 回合制战斗模拟游戏

## 特性

- 🦖 **70只史前动物** —— 从霸王龙到虾蛄，每只动物有独特的六维属性评级（攻击/防御/机动/技巧/续航/智商）
- ⚔️ **三种战斗规模** —— 1v1 单挑、3v3 小队战、5v5 大乱斗
- 🎲 **抽卡 Ban 场模式** —— 随机抽卡 → 编队 → 先手判定 → 轮流禁用战场 → 环境淘汰与替补顶替
- 🛠️ **自定义组队模式** —— 自由选择阵容，调整突发事件概率
- 🎮 **逐回合操纵** —— 每回合设置阵型（前排/后排）和战术策略（常规/狂暴/坚守/游击）
- 🌟 **14种突发事件** —— 陨石撞击、冰期骤降、博物馆之夜、时间褶皱……
- 📊 **六维雷达图** —— 可视化每只动物在不同战场的属性分布
- 💾 **数据持久化** —— 玩家账号、战斗历史、排行榜全部保存
- 🎨 **精美暗色主题** —— 金色点缀，粒子背景动画

## 快速开始

```bash
# 1. 安装依赖
pip install fastapi uvicorn pydantic

# 2. 启动服务器
python server.py

# 3. 浏览器打开
http://localhost:8767
```

## 项目结构

```
├── server.py          # FastAPI 后端 + SQLite 数据库
├── requirements.txt   # Python 依赖
└── static/
    ├── index.html     # 前端主页面
    ├── style.css      # 样式系统
    ├── game-data.js   # 70只动物数据
    ├── engine.js      # 回合制战斗引擎
    ├── ui.js          # UI 渲染
    └── app.js         # 应用逻辑
```

## 技术栈

- **后端**: Python + FastAPI + SQLite
- **前端**: 原生 HTML/CSS/JS（无框架依赖）
- **战斗引擎**: 完整移植自 Python `battle_engine.py`，含属性评级→数值转换、伤害公式、先手判定、替补顶替等逻辑

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/players/register` | 注册玩家 |
| POST | `/api/players/login` | 登录 |
| GET  | `/api/players/{id}/stats` | 玩家统计 |
| GET  | `/api/leaderboard` | 排行榜 |
| POST | `/api/battles` | 保存战斗记录 |
| GET  | `/api/players/{id}/battles` | 战斗历史 |
| GET/POST/PUT/DELETE | `/api/players/{id}/teams` | 编队管理 |

## License

MIT
