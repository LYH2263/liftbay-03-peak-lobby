# LiftBay

电梯派梯：同向优先与楼层距离评分，轿厢满员拒绝派工。

## 早高峰模式

- 楼栋页可开关「早高峰」，状态入库，刷新/重进仍显示库中状态。
- 开启后：大厅层（楼栋的 `lobby_floor`，种子指定）的上行呼梯优先派给当前停在大厅且空闲或同向上行的轿厢，即使其他同向轿厢按普通评分更高；非大厅层呼梯仍走同向+距离评分。
- 高峰优先与满员冲突时不超载：满员大厅车自动失去高峰资格，改派次选；全部满员则拒绝。
- 回放页记录每次派工是否因高峰改写了胜者（高峰改写 / 高峰 / —）。

## 启动

```bash
docker compose up --build
```

| 服务 | 地址 |
| --- | --- |
| 前端 | http://localhost:4200 |
| API | http://localhost:9200 |
| API 文档 | http://localhost:9200/docs |
| Postgres | localhost:5443 |

健康检查：`GET http://localhost:9200/api/health`

## 页面

- `/buildings` — 楼栋
- `/cars` — 轿厢
- `/calls` — 呼梯
- `/dispatch` — 派工
- `/replay` — 回放
- `/congestion` — 拥堵

## 使用说明

1. 查看楼栋与轿厢状态。
2. 在呼梯页登记请求，在派工页按评分分配轿厢。
3. 回放页查看派工轨迹，拥堵页查看高峰楼层。

## 开发与测试

```bash
docker compose exec api pytest -q
```
