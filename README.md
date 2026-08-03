# 同花顺板块趋势早报

每天上午 11:00 获取同花顺行业板块盘中数据，生成带热力图、20 日趋势和规则化信号的 HTML 邮件。默认由 `tfy1317262462@126.com` 发给自己。

## 一、环境准备

建议使用 Python 3.11：

```powershell
cd "E:\1-私募\7-分版块趋势"
py -3 -m pip install -r requirements.txt
```

项目已固定在本机验证过的 `akshare==1.18.64`。升级 AKShare 前请先执行 dry-run，确认同花顺字段没有变化。

## 二、126 邮箱授权码

1. 登录 126 邮箱网页，在客户端/POP3/SMTP 设置中启用 SMTP 服务。
2. 创建“客户端授权码”。授权码不是网页登录密码。
3. 在 PowerShell 中设置用户级环境变量：

```powershell
[Environment]::SetEnvironmentVariable("SMTP_AUTH_CODE", "你的客户端授权码", "User")
```

设置后请重新打开终端。不要把授权码写进 `config.yaml`、脚本或代码。

可在新终端中只检查变量是否存在，不打印真实值：

```powershell
if ($env:SMTP_AUTH_CODE) { "授权码已加载" } else { "授权码未加载" }
```

## 三、运行命令

### 生成本地预览，不发邮件

```powershell
py -3 -m sector_report run --dry-run
```

结果保存在 `output\YYYY-MM-DD\report.html`。打开该文件即可检查邮件版式。

### 初始化或修复历史数据

```powershell
py -3 -m sector_report backfill
```

### 正式发送

```powershell
py -3 -m sector_report run --send
```

程序只在 A 股交易日发送。下午 12:30 后手工执行时默认不会补发已经过时的早报；测试时可显式添加 `--force`，但 `--force --send` 可能产生重复邮件。

## 四、创建 Windows 定时任务

在 PowerShell 中运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\setup_task.ps1
```

脚本创建“同花顺板块趋势早报”任务：

- 周一至周五 11:00 启动；
- 程序内部再次检查 A 股交易日；
- 允许唤醒睡眠中的电脑；
- 错过触发后尽快运行，但程序超过 90 分钟不再发送；
- 同一日期成功发送后不会再次正式发送。

定时任务采用当前用户的交互式登录身份。电脑完全关机或用户未登录时不能保证准时运行。

## 五、配置

编辑 `config.yaml` 可以修改：

- 收发邮箱和 SMTP 地址；
- 数据库、输出目录和请求间隔；
- 最大补发时间；
- 信号阈值；
- 主题分组和重点行业名单。

行业名称必须与 AKShare 的同花顺行业名称完全一致。当前默认 20 个板块分为消费、科技、医疗、光电新能源和传统能源五组。

## 六、数据文件与日志

- SQLite 数据库：`data\sector_report.db`
- 运行日志：`data\sector_report.log`
- 邮件预览：`output\YYYY-MM-DD\report.html`
- CID 邮件原文：`output\YYYY-MM-DD\report_email.html`
- 图表：同一日期输出目录中的 PNG 文件

数据库和输出目录默认不纳入 Git。

## 七、故障处理

- **字段结构变化**：程序会拒绝生成报告并记录缺少的字段，避免静默发送错误行情。
- **网络或限流**：请求最多重试三次，并在板块历史请求之间等待。
- **实时数据失败**：不使用旧行情冒充当天报告；如授权码可用，会发送采集失败告警。
- **SMTP 失败**：本地 HTML 和图表仍会保留，可根据日志排查后重新发送。
- **首次运行趋势为空**：先执行 `backfill`，或直接运行 dry-run；程序会自动回填至少 90 个自然日。

## 八、测试

```powershell
py -3 -m pytest
```

端到端验收建议依次执行：

1. `backfill`
2. `run --dry-run`
3. 检查本地 HTML 与图片
4. 设置授权码后执行一次 `run --send --force`
5. 确认 126 邮箱收到正文图片完整的邮件
