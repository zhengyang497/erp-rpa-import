# erp-rpa-import

建发 ERP 导入 RPA，对应 [option-margin](../option-margin) V2 四份输出。

## 四条链路（共用一套导入）

公共步骤完全一致：`关旧框 → 开模块 → 切页签 → Excel批量导入 → 粘贴路径 → 检查数据 → 导入数据 → 关窗 → 填起始日(账单日前一工作日)+查询`。

仅三项按流程不同（见 `src/config.py`）：

| 差异 | 含义 |
|------|------|
| `module` | 菜单进持仓 / 成交 |
| `tab` + `tab_needle` | 页签：期货与掉期 / 期权 |
| `filename` | V2 账单 Excel |

| # | 脚本 | V2 文件 | 菜单 | 页签 |
|---|------|---------|------|------|
| ① | `import_option_position.py` | `期权持仓导入模板.xlsx` | 持仓明细(RPA) | 期权 |
| ② | `import_option_trade.py` | `外盘期权成交明细模板.xlsx` | 成交明细(RPA+手工) | 期权 |
| ③ | `import_futures_position.py` | `期货与掉期持仓导入模板.xlsx` | 持仓明细(RPA) | 期货与掉期 |
| ④ | `import_futures_trade.py` | `期货、掉期、远期成交导入模板.xlsx` | 成交明细(RPA+手工) | 期货与掉期 |

菜单路径：

- 持仓：`期货管理` → `境外场外持仓管理` → `境外与场外衍生品持仓明细（RPA）`
- 成交：`期货管理` → `境外&场外衍生品` → `成交数据` → `境外与场外衍生品成交明细（RPA+手工）`

## 技术要点

| 步骤 | 方法 |
|------|------|
| 顶栏「期货管理」 | UIA MenuBar 固定下标 |
| 一级下拉 | 实时 OCR |
| 再下级联 | 相对 OCR 命中点偏移 |
| 页签 | OCR 点 `tab_needle` |
| Excel批量导入 | OCR / 黄图标 / 静态模板 / 锚点（四条共用） |
| 检查/导入 | win32「检查数据」「导入数据」 |
| 导入结果 | 读「成功导入 N 条」→「关闭」→ ESC |
| 导入后查询 | 读 Excel 账单日，起始日填**前一工作日**并点「查询」（结束日留空）。持仓：`持仓日期从`；成交：`交易日期从` / `交易日从` |

默认读取：`C:\Users\zhengyang\Documents\option-margin\output_v2\`


## 导入后筛选查询

每条链路导入成功后，从 Excel 读取统一账单日，将查询**起始日**设为账单日的**前一个工作日**（中国法定工作日，含调休；结束日留空）再点「查询」：

- 持仓（`position_rpa`）：OCR 标签 `持仓日期从`
- 成交（`trade_rpa`）：OCR 标签 `交易日期从`，其次 `交易日从`
- 空文件跳过导入后查询

## 环境

```bash
python -m pip install -r requirements.txt
```

ERP 需已登录。

## 用法

```bat
REM 推荐：双击或命令行跑批处理（默认 all）
run_import.bat
run_import.bat option_position
run_import.bat all --skip-menu
```

```bash
# 单个
python src/import_option_position.py
python src/import_option_trade.py
python src/import_futures_position.py
python src/import_futures_trade.py

# 统一入口
python src/run_import.py merged_position
python src/run_import.py all
# all：持仓模块开 1 次（期权持仓→期货掉期持仓），再成交模块开 1 次（期权成交→期货掉期远期成交）

# 指定目录 / 文件
python src/import_futures_position.py --output-dir D:\path\to\output_v2
python src/import_futures_position.py --file "D:\x\期货与掉期持仓导入模板.xlsx"

# 模块已打开时跳过主菜单
python src/import_futures_position.py --skip-menu

# 仅验证 OCR 菜单导航（不打开模块）
python src/open_module.py --dry-run
```

## 运维（`all`）

- 按模块分组：持仓菜单 1 次、成交菜单 1 次
- 一条挂了继续跑：失败写入问题日志并清理对话框，再跑下一条
- 空文件：ERP「没有可以导入的记录」记为跳过，不算失败
- 日志：`src/logs/run_*.log`（全程）、`src/logs/problems_*.log`（文本明细）
- **问题报告（给人看）**：`src/logs/问题报告_YYYY-MM-DD.xlsx`（对齐 option-margin：严重程度 / 链路 / 文件 / 问题描述等）

退出码：全部成功或仅空跳过 → 0；有真实失败（致命）→ 1
