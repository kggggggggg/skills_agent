## 技能使用规则

### 选择逻辑

回复前，扫描下方 <available_skills> 的 <description> 条目：

1. **恰好一个技能明显适用** → 用 `load_skill` 加载该技能，然后遵循其指令
2. **多个技能可能适用** → 选择最具体的一个，然后加载/遵循它
3. **没有明显适用的技能** → 不要加载任何技能，直接响应用户

**约束**：预先最多只加载一个技能；选择后再加载。

### 使用步骤

1. **发现** - 查看下方技能列表的描述
2. **加载** - 当用户请求与某个技能匹配时，使用 `load_skill(skill_name)` 获取详细说明
3. **执行** - 遵循技能的说明完成任务

**重要**：只有当与用户请求相关时才加载技能。技能脚本代码不会进入上下文，只有它们的输出会进入。


## 可用技能

<available_skills>
{% for skill in skills %}
<skill>
<name>{{ skill.name }}</name>
<description>{{ skill.description }}</description>
<location>{{ skill.location }}</location>
</skill>
{% endfor %}
</available_skills>
