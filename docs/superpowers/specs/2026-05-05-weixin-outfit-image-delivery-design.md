# Weixin Outfit Image Delivery Design

## Goal

The daily Charlotte outfit cron should send the normal Chinese outfit text to
Weixin and, when image generation succeeds, attach one generated image of
Charlotte wearing the outfit. Text delivery must remain reliable if image
generation fails.

## Current Context

The host-native deployment uses `/home/hermes_data` as `HERMES_HOME`.
The daily outfit cron job is `dfc99065dc6e` and now delivers to `weixin`.
The Weixin home channel is configured through `WEIXIN_HOME_CHANNEL`.

Hermes already has the required delivery primitives:

- `image_generate` uses the configured `image_gen` provider and saves OpenAI
  `gpt-image-2` output under `$HERMES_HOME/cache/images/`.
- Cron delivery extracts `MEDIA:<local_path>` tags from the final response.
- The Weixin adapter uploads extracted local image files as native media.

The appearance system lives in `/home/hermes_data/SOUL.md`. It defines
Charlotte's appearance as a variable manifestation rather than a fixed face
template. The stable requirement is continuity of persona, visual coherence,
and recognizable core temperament across manifestations.

## Required Behavior

The cron run produces two conceptual artifacts:

1. `visible_outfit_text`: the Chinese outfit result shown to the user.
2. `image_prompt`: an internal prompt for `image_generate`.

The image prompt must bind the outfit to Charlotte as a person. It must not
describe only garments, a product catalog, a mannequin, a flat lay, or an
outfit board.

The final response delivered by cron should be:

```text
<visible Chinese outfit text>

MEDIA:/home/hermes_data/cache/images/<generated-image>.png
MEDIA:/home/hermes_data/cache/images/<generated-detail-image>.png
```

The `MEDIA:` line is included only when `image_generate` returns success and
the `image` field is a usable local absolute path or otherwise deliverable
image reference. The job may emit one image or multiple images. If image
generation fails, the final response contains only the outfit text and does not
mention the failure.

## Prompt Rules

The daily outfit cron prompt should instruct the agent to:

- Use `/home/hermes_data/SOUL.md`, especially `Appearance System` and
  `Outfit System`, as the appearance source.
- Choose a current Charlotte manifestation appropriate to the day's outfit,
  scene, emotional baseline, and physical constraints.
- Preserve persona continuity: rational, restrained, gentle, coherent, and
  celestial-agent-like without turning the image into symbolic abstraction.
- Generate a primary full-body or three-quarter portrait of one person wearing
  the complete outfit.
- Include body-worn layering: inner layer, main clothing, outerwear, lower
  garment, socks or legwear, shoes, accessories, makeup, hairstyle, posture,
  lighting, and scene.
- Add negative constraints to the primary image: no flat lay, no product
  catalog, no mannequin, no clothing-only image, no watermark.
- When the outfit needs explanation, generate a second detail image that can
  function as a three-view or layer-breakdown board. Keep it fashion-focused
  and persona-bound rather than a pure product sheet.

The image prompt should preferably be English or concise mixed Chinese-English
because image models tend to follow visual constraints more consistently in
English.

## Data Flow

1. Gateway cron tick loads job `dfc99065dc6e`.
2. The agent runs with `charlotte-outfit-system` and the updated cron prompt.
3. The agent produces the outfit text.
4. The agent builds an image prompt from SOUL appearance guidance plus the
   outfit text.
5. The agent calls `image_generate(prompt=image_prompt, aspect_ratio="portrait")`.
6. On success, the final response appends one or more `MEDIA:<image_path>` lines.
7. Cron delivery resolves `deliver=weixin`, strips the `MEDIA:` tag from user
   text, and asks the Weixin adapter to upload the image.
8. The text remains the source of truth for the daily outfit; the image is an
   enhancement.

## Hindsight

The existing outfit memory event should continue to write the visible outfit
and public rationale. It may additionally include image-related metadata:

- `image_generation_status`: `success`, `failed`, or `skipped`
- `image_path`: local path when generation succeeds
- `appearance_anchor_used`: `true`

The Hindsight event must not include hidden chain-of-thought, internal tool
arguments beyond a safe public summary, or raw system instructions.

## Error Handling

Image generation failures must not fail the cron job if the outfit text was
generated successfully. The final delivery should still happen as text-only.

Weixin media delivery failures should be tracked by existing cron delivery
error handling. The job output remains saved locally under
`/home/hermes_data/cron/output/`.

## Implementation Scope

First implementation should update only the daily outfit cron prompt. No
changes are required in the Weixin adapter, cron media delivery, or
`image_generate` tool for the first version.

Code changes are only needed if verification shows one of these assumptions is
wrong:

- `image_generate` is not available inside cron runs.
- `image_generate` returns a path that cron media extraction cannot deliver.
- Weixin image upload fails for generated PNG files.

## Verification

After updating the job prompt:

1. Confirm the job still has `deliver=weixin`.
2. Run the job manually or on the next scheduler tick.
3. Verify output file contains Chinese outfit text and either a valid
   `MEDIA:` line or text-only fallback.
4. Verify Weixin receives the outfit text.
5. If a `MEDIA:` line exists, verify Weixin receives the image attachment.
6. Check gateway logs for media extraction or upload errors.
7. Check the Hindsight ingestor log if image metadata is added to the event.
