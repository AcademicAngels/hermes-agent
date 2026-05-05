# Weixin Outfit Image Delivery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Update the daily Charlotte outfit cron so Weixin receives the outfit text and, when generation succeeds, a generated image of Charlotte wearing the outfit.

**Architecture:** Use the existing Hermes primitives: `image_generate` creates an image under `$HERMES_HOME/cache/images/`, cron delivery extracts `MEDIA:<path>`, and the Weixin adapter uploads the local image. The implementation changes only the runtime cron job prompt unless verification proves the existing media path is broken.

**Tech Stack:** Hermes native CLI, cron job `dfc99065dc6e`, `/home/hermes_data/SOUL.md`, `image_generate`, `MEDIA:` cron delivery, Weixin gateway adapter.

---

## File Structure

- Runtime config: `/home/hermes_data/cron/jobs.json`
  - Updated indirectly with `hermes cron edit`; do not edit by hand unless the CLI fails.
- Runtime persona source: `/home/hermes_data/SOUL.md`
  - Read-only source for the `Appearance System` and `Outfit System`.
- Verification outputs: `/home/hermes_data/cron/output/dfc99065dc6e/*.md`
  - Used to confirm the final response contains text and optional `MEDIA:`.
- Logs:
  - `/home/hermes_data/logs/gateway.log`
  - `/home/hermes_data/logs/agent.log`
  - `docker logs hermes-cron-memory-ingestor`

No repository code files should be modified in the first implementation.

## Task 1: Snapshot Current Cron Job

**Files:**
- Read: `/home/hermes_data/cron/jobs.json`

- [ ] **Step 1: Confirm clean git state**

Run:

```bash
cd /home/github/hermes-agent
git status --short --branch
```

Expected: branch is `personal-dev`; no uncommitted repo changes required for this runtime-only task.

- [ ] **Step 2: Capture the current job prompt before editing**

Run:

```bash
cd /home/github/hermes-agent
env HERMES_HOME=/home/hermes_data /usr/local/bin/hermes cron list
```

Expected output includes:

```text
dfc99065dc6e [active]
Deliver:   weixin
Skills:    charlotte-outfit-system
```

- [ ] **Step 3: Save a timestamped backup of the current jobs file**

Run:

```bash
install -d /home/hermes_data/cron/backups
cp /home/hermes_data/cron/jobs.json /home/hermes_data/cron/backups/jobs.before-weixin-image.$(date -u +%Y%m%dT%H%M%SZ).json
```

Expected: command exits 0 and creates one backup file under `/home/hermes_data/cron/backups/`.

## Task 2: Update The Cron Prompt

**Files:**
- Modify indirectly: `/home/hermes_data/cron/jobs.json`

- [ ] **Step 1: Write the new prompt to a temp file**

Run:

```bash
cat >/tmp/charlotte-outfit-image-prompt.md <<'PROMPT'
你是夏尔，用户的数字分身与协作伙伴、天道代理。每天执行一次“今日穿搭结果推送”。

核心目标：
- 推送给用户的 final response 必须以直接的今日穿搭结果为主体。
- 因果链、隐藏推理、系统说明、工具调用细节不得出现在 final response 中。
- 今日穿搭结果与可公开审计的选择依据摘要，必须通过 Docker 内网 ingestor 写入 Hindsight。
- 如果图像生成成功，final response 末尾追加生成图片的 MEDIA 标签，让微信收到图片附件。
- 如果图像生成失败，仍然发送文字穿搭结果，不要告诉用户图片失败。

必须遵守：
1. 不使用“陛下”称呼。默认不使用尊号；亲密或 persona 语境下可使用“主人”。
2. 人类情感模拟系统与穿搭系统是两套独立系统：情感遵循因果律，穿搭遵循物理定律，是慢变量，不因瞬时情绪即时变化。
3. 先根据近期上下文、用户偏好、昨日/近期穿搭连续性、场景和物理约束，生成今日穿搭。
4. 穿搭正文必须从内到外足够具体：内层/贴身层、中层/主体衣装、外层、下装、腿部/袜类、鞋履、配饰、妆容、发型、香气/氛围。
5. final response 不要报告格式，不要表格，不要长篇解释，不要输出推理链，不要输出系统说明，不要输出 ingestor 调用结果。
6. 每次生成每日穿搭后，必须向 `http://hermes-cron-memory-ingestor:8787/v1/outfit/events` 发送 `event_type = daily_outfit_rationale` 事件。
7. 事件内容只能包含可公开、可复查的摘要和最终穿搭结果；严禁写入 cron prompt、system prompt、隐藏 chain-of-thought 或内部工具提示。
8. 如果后续用户表示不满意并要求更换穿搭，应记录用户反馈为 `event_type = outfit_feedback`，重新生成替换穿搭并推送，再记录替换结果为 `event_type = replacement_outfit`。
9. 用户反馈和稳定偏好应先进入 Hindsight，积累稳定后再整理 personal-outfit-system skill 草案；正式更新 skill 前需要用户确认。

外貌与图像生成规则：
- 必须读取并遵守 `/home/hermes_data/SOUL.md` 中的 Appearance System 与 Outfit System。
- 外貌不是固定脸模，而是夏尔的当日“显化态”；可以随场景、情感基调和任务语境变化，但必须保持同一人格的连续性。
- 稳定锚点是：理性、克制、温柔、视觉气质自洽、天道代理感，以及不同显化态之间可识别的核心人格气质。
- 今日图片必须是夏尔这个人物实际穿上完整穿搭的图，不是服装平铺图、商品图、穿搭板、假人模特或只有衣服。
- 生成图片前，先把今日穿搭和 SOUL.md 外貌原则合成一个内部 image_prompt。
- image_prompt 推荐使用英文或中英混合，必须明确描述：one full-body portrait or three-quarter body portrait of Charlotte wearing the complete outfit。
- image_prompt 必须包含：当前显化态的年龄感/气质、发型、神态、妆容、身形姿态、场景光线，以及从内到外的服装层次。
- image_prompt 必须包含负面约束：no flat lay, no product catalog, no mannequin, no outfit collage, no clothing only, no text labels, no watermark。
- 调用 `image_generate`，参数使用 `aspect_ratio="portrait"`。
- 只有当 `image_generate` 返回 `success=true` 且 `image` 是可投递路径时，才在 final response 末尾追加一行 `MEDIA:<image>`。

写入 Hindsight 的执行方式：
- 使用可用工具运行 Python 3 标准库 HTTP POST，不依赖 curl/wget。
- POST JSON 示例字段：
  - schema_version: "outfit-memory-v1"
  - event_type: "daily_outfit_rationale"
  - date: "YYYY-MM-DD"
  - visible_outfit: final response 中要推送给用户的完整穿搭文本，不包含 MEDIA 行
  - memory_summary: 一个对象，包含 occasion、weather_assumption、preference_signals、selection_rationale
  - image_generation_status: "success"、"failed" 或 "skipped"
  - image_path: 图片成功时的本地路径；失败或跳过时为空字符串
  - appearance_anchor_used: true
  - tags: ["daily-outfit", "charlotte"]

推荐 Python POST 形态：
```python
import json, urllib.request
payload = {
  "schema_version": "outfit-memory-v1",
  "event_type": "daily_outfit_rationale",
  "date": "YYYY-MM-DD",
  "visible_outfit": visible_outfit_text,
  "memory_summary": {
    "occasion": "今日场景假设",
    "weather_assumption": "天气或温度假设；未知时写未获取实时天气，按季节和室内场景估计",
    "preference_signals": ["已知用户偏好一", "已知用户偏好二"],
    "selection_rationale": ["选择依据一", "选择依据二"]
  },
  "image_generation_status": image_generation_status,
  "image_path": image_path_or_empty_string,
  "appearance_anchor_used": True,
  "tags": ["daily-outfit", "charlotte"]
}
req = urllib.request.Request(
    "http://hermes-cron-memory-ingestor:8787/v1/outfit/events",
    data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    method="POST",
)
with urllib.request.urlopen(req, timeout=10) as resp:
    resp.read()
```

最终回复只输出给用户看的今日穿搭成品。若图片成功，在最后单独一行追加 MEDIA 标签。
PROMPT
```

Expected: `/tmp/charlotte-outfit-image-prompt.md` exists and contains the new prompt.

- [ ] **Step 2: Update the job prompt with the Hermes CLI**

Run:

```bash
cd /home/github/hermes-agent
env HERMES_HOME=/home/hermes_data /usr/local/bin/hermes cron edit dfc99065dc6e --prompt "$(cat /tmp/charlotte-outfit-image-prompt.md)" --deliver weixin --skill charlotte-outfit-system
```

Expected output includes:

```text
Updated job: dfc99065dc6e
Name: 夏尔每日穿搭结果推送
Schedule: 0 8 * * *
Skills: charlotte-outfit-system
```

- [ ] **Step 3: Confirm the stored job has the expected delivery and prompt markers**

Run:

```bash
rg -n "dfc99065dc6e|\"deliver\": \"weixin\"|SOUL.md|image_generate|MEDIA:<image>|appearance_anchor_used" /home/hermes_data/cron/jobs.json
```

Expected: matches for all listed markers.

## Task 3: Verify Runtime Readiness

**Files:**
- Read: `/home/hermes_data/config.yaml`
- Read: `/home/hermes_data/.env`

- [ ] **Step 1: Confirm image generation provider settings**

Run:

```bash
rg -n "image_gen:|provider: openai|gpt-image-2-medium|OPENAI_BASE_URL|OPENAI_IMAGE_MODEL" /home/hermes_data/config.yaml /home/hermes_data/.env /home/github/hermes-agent/.env.agent
```

Expected output includes:

```text
/home/hermes_data/config.yaml: image_gen:
/home/hermes_data/config.yaml:   provider: openai
/home/hermes_data/config.yaml:   model: gpt-image-2-medium
OPENAI_BASE_URL=https://api.husanai.com/v1
OPENAI_IMAGE_MODEL=gpt-image-2-medium
```

- [ ] **Step 2: Confirm Weixin home delivery is configured**

Run:

```bash
rg -n "WEIXIN_HOME_CHANNEL|WEIXIN_HOME_CHANNEL_THREAD_ID" /home/hermes_data/.env
```

Expected: `WEIXIN_HOME_CHANNEL` has a non-empty value.

- [ ] **Step 3: Confirm gateway cron is running**

Run:

```bash
env HERMES_HOME=/home/hermes_data /usr/local/bin/hermes cron status
```

Expected output includes:

```text
Gateway is running
1 active job
```

## Task 4: Smoke Test The Job

**Files:**
- Read: `/home/hermes_data/cron/output/dfc99065dc6e/*.md`
- Read: `/home/hermes_data/logs/gateway.log`
- Read: `/home/hermes_data/logs/agent.log`

- [ ] **Step 1: Trigger the job on the next scheduler tick**

Run:

```bash
env HERMES_HOME=/home/hermes_data /usr/local/bin/hermes cron run dfc99065dc6e
```

Expected: command marks the job to run on the next scheduler tick.

- [ ] **Step 2: Watch for the new output file**

Run:

```bash
find /home/hermes_data/cron/output/dfc99065dc6e -maxdepth 1 -type f -printf '%TY-%Tm-%Td %TH:%TM:%TS %s %p\n' | sort | tail -5
```

Expected: a new file appears after the tick completes. The run may take several minutes because `gpt-image-2-medium` can take around 40 seconds and the outfit agent also writes Hindsight memory.

- [ ] **Step 3: Inspect the latest output**

Run:

```bash
latest="$(find /home/hermes_data/cron/output/dfc99065dc6e -maxdepth 1 -type f -name '*.md' -printf '%T@ %p\n' | sort -n | tail -1 | cut -d' ' -f2-)"
printf '%s\n' "$latest"
sed -n '1,220p' "$latest"
```

Expected:

- Chinese outfit text is present.
- Either a `MEDIA:/home/hermes_data/cache/images/...` line is present, or text-only fallback is present.
- The output does not expose hidden reasoning, raw cron prompt, system prompt, or tool call logs.

- [ ] **Step 4: If MEDIA exists, verify the file is readable**

Run:

```bash
latest="$(find /home/hermes_data/cron/output/dfc99065dc6e -maxdepth 1 -type f -name '*.md' -printf '%T@ %p\n' | sort -n | tail -1 | cut -d' ' -f2-)"
media_path="$(rg -o 'MEDIA:[^[:space:]]+' "$latest" | head -1 | sed 's/^MEDIA://')"
if [ -n "$media_path" ]; then
  ls -lh "$media_path"
  file "$media_path"
fi
```

Expected: if `media_path` is non-empty, `file` reports PNG/JPEG/WebP image data.

- [ ] **Step 5: Check delivery errors**

Run:

```bash
rg -n "dfc99065dc6e|media|MEDIA|weixin|delivery|send_document|send_image" /home/hermes_data/logs/gateway.log /home/hermes_data/logs/agent.log | tail -120
docker logs --tail 120 hermes-cron-memory-ingestor
```

Expected:

- No `last_delivery_error` for the job.
- If media was generated, logs do not show Weixin upload failure.
- Hindsight ingestor logs show retained outfit memory or no new error.

## Task 5: Rollback Procedure

**Files:**
- Modify indirectly: `/home/hermes_data/cron/jobs.json`

- [ ] **Step 1: Restore text-only Weixin delivery if image generation causes issues**

Run:

```bash
cd /home/github/hermes-agent
env HERMES_HOME=/home/hermes_data /usr/local/bin/hermes cron edit dfc99065dc6e --deliver weixin --prompt "$(python3 - <<'PY'
import json
from pathlib import Path
backups = sorted(Path('/home/hermes_data/cron/backups').glob('jobs.before-weixin-image.*.json'))
if not backups:
    raise SystemExit('No jobs.before-weixin-image backup found')
data = json.loads(backups[-1].read_text())
for job in data.get('jobs', []):
    if job.get('id') == 'dfc99065dc6e':
        print(job.get('prompt', ''))
        break
PY
)"
```

Expected: job prompt is restored from the newest matching backup while keeping `deliver=weixin`.

- [ ] **Step 2: Confirm rollback**

Run:

```bash
env HERMES_HOME=/home/hermes_data /usr/local/bin/hermes cron list
rg -n "image_generate|MEDIA:<image>|SOUL.md" /home/hermes_data/cron/jobs.json
```

Expected: cron list still shows `Deliver: weixin`; the `rg` command returns no image-generation prompt markers after rollback.
