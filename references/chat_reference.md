# Chat Reference

## 中文触发示例

用户可能会这样说：

- `今天做了接口联调、修复登录问题、跟进发布。`
- `帮我记一下我今天完成了三件事：整理需求、开评审会、修了支付回调。`
- `这项工作属于支付项目，分类算研究。`
- `看看我昨天都做了什么。`
- `把这周的工作进度总结一下。`
- `先记一下今天的工作，再帮我出这周总结。`
- `把 2026-03-31 的日报改一下，实际做的是 A 和 B。`
- `把刚才那条任务的项目改成 auth-stability，分类改成 development。`

## Record Work

User prompt:

`今天完成了接口联调、修了登录 bug，还卡在测试环境配置。都属于 auth-stability 项目，前两个算 development，最后一个算 operations。`

Suggested action:

1. Resolve the target date.
2. Build one item per task.
3. Mark the unfinished blocker as `blocked`.
4. Preserve `project` and `category` on each item.
5. Run `record`.

Example payload:

```json
[
  {
    "task": "Completed API integration",
    "status": "done",
    "project": "auth-stability",
    "category": "development"
  },
  {
    "task": "Fixed login bug",
    "status": "done",
    "project": "auth-stability",
    "category": "development"
  },
  {
    "task": "Testing environment configuration",
    "status": "blocked",
    "project": "auth-stability",
    "category": "operations",
    "details": "Blocked while waiting for environment access"
  }
]
```

## Read One Day

User prompt:

`帮我看下 2026-03-31 我做了什么，按项目和分类一起看。`

Suggested action:

Run `day-report --date 2026-03-31` and summarize the returned entries, project
counts, and category counts in the user's language.

## Replace One Day

User prompt:

`把 2026-03-31 的日报改一下，之前记错了，应该是接口联调和发布回归，都算 auth-stability 项目。`

Suggested action:

1. Resolve the explicit target date.
2. Build the corrected full set of entries for that day.
3. Run `replace-day --date 2026-03-31 --items-json ...`.
4. Treat the result as the source of truth for the corrected day.

## Update One Entry

User prompt:

`把刚才那条“测试环境配置”的状态改成已完成，项目还是 auth-stability，分类改成 development。`

Suggested action:

1. Resolve the target entry from `day-report` or `week-report`.
2. Extract its `id`.
3. Run `update-entry --entry-id ...` with only the changed fields.
4. Keep the rest of the entry unchanged.

## Delete One Entry

User prompt:

`把刚才那条“测试环境配置”删掉，这个不该记进去。`

Suggested action:

1. Resolve the target entry from `day-report` or `week-report`.
2. Extract its `id`.
3. Run `delete-entry --entry-id ...`.
4. Confirm the removed task from the command output.

## Read Entry History

User prompt:

`帮我看下这条任务改过几次，项目和分类有没有变。`

Suggested action:

1. Resolve the target entry id.
2. Run `entry-history --entry-id ...`.
3. Summarize the versions in chronological order, including project/category
   changes when present.

## Read Day History

User prompt:

`帮我看下 2026-03-31 的日报后来被改过哪些内容，按项目和分类一起看。`

Suggested action:

1. Resolve the explicit target date.
2. Run `day-history --date 2026-03-31`.
3. Summarize the affected entries and their change sequence.

## Summarize One Week

User prompt:

`把这周的工作进度总结一下，顺便按项目和分类归一下。`

Suggested action:

Run `week-report` with an anchor date inside the requested week, then report:

- exact week range
- per-day recorded work
- project counts
- category counts
- any `blocked` or `in_progress` items

When the user is writing in Chinese, read `chinese_output.md` before answering.

## Multi-Day Import

User prompt:

`周一完成了版本发布，周二处理了两个线上问题，周三学了课程。`

Suggested action:

Run one `record` command per date instead of mixing multiple dates into a
single command.
