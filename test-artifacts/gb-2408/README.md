# 两点组记录对账 · 验证记录（gb-2408）

## 测试文件
- `test_matching.py` — 算法对拍：`PYTHONPATH=/workspace/backend python3 test_matching.py`
- `test_service.py` — 服务层集成（SQLite内存库+假Redis）：`PYTHONPATH=/workspace/backend python3 test_service.py`
- `test-log.txt` — 最近一次全量回归输出

## 覆盖
1. 暴力枚举对拍：400个随机小图（n,m≤6，含重合坐标/零阈值/并列代价），逐对核对
   最优对数、可配集合、必然集合、双侧点状态、报告方案最优性（量化总代价一致）。
2. 确定性：同一输入两次运行结果逐字节一致；校验和只覆盖快照与确定性输出。
3. 重合坐标：3左2右同坐标各占名额，6对全歧义；孤立点始终未配。
4. 全重合300×300：90000对全歧义，0.69秒（上限10秒）。
5. 密集300×300全候选：0.38秒。
6. 大坐标1e9平移、阈值边界d2==t2、空候选、字典序（代价并列→歧义，代价不同→必然）。
7. 超时：过期deadline抛ReconcileTimeout，不落任何部分结果。
8. 服务层：创建冻结双方来源与阈值、重名409/缺测组404/缺点组422、阈值schema拒绝
   0/负/inf/nan、queued→completed落库、列表摘要不带完整结果、原测组未被修改。
9. seed演示对账交叉核对：左始终未配=阈值内无候选的5点，右始终未配=5个新增点，
   报告方案每点最多配一次。

## 结果
全部通过。最近回归：brute-force x400 OK / determinism OK / coincident OK /
timeout OK / dense 300x300 0.38s / service integration OK / checksum deterministic OK。
前端 `npm run build`（vue-tsc + vite）通过；后端 `python3 -m py_compile` 通过。
