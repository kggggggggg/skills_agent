---
name: time-and-env
description: 当用户询问“当前时间/时区/运行环境信息”时，用 bash 获取并以固定格式返回（适合做 skills demo）。
---

# time-and-env（时间与环境信息）

## 适用场景

- “现在几点了 / 今天几号 / 当前时区是什么”
- “你在哪个目录运行 / 当前环境变量有没有加载”

## 工作流程

1) 优先运行本技能自带脚本（避免多次 tool call，输出也更稳定）：
   - `bash("bash .skills/time_and_env/scripts/time_and_env.sh")`

2) 如果脚本不可用，再退回到直接执行：
   - `bash("date")`
   - `bash("pwd")`

3) 用以下固定格式返回（演示 skill 的价值：统一输出风格）：
   - `时间`: 直接使用 `date` 输出
   - `目录`: 直接使用 `pwd` 输出
   - `答复`: 1~3 句回答用户问题
