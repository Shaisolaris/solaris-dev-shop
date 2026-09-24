# Blender Motion-State Inspection (structured rig/pose/contact debugging)

Methodology absorbed from ECC `blender-motion-state-inspection` (affaan-m/ECC, MIT). Net-new vs blender-backbone.md, which covers the blender-mcp tooling + static cleanup pass but NOT how to debug a moving rig. This is the debugging discipline for the game pipeline: when an imported avatar or retargeted clip looks twisted, mirrored, flat, offset, or foot-sliding.

## Core principle: facts before screenshots
A viewport screenshot is review evidence, not proof. It hides axis conventions, bone names, object scale, local transforms, parented meshes, material slots, and per-frame contact state. First extract structured Blender state, THEN use a render/screenshot to confirm what the facts already imply. blender-mcp gives both viewport screenshots and `execute_blender_code` (Python in Blender) - use the Python path to pull the facts, screenshots only to confirm.

## When to run this (not the static cleanup pass)
- A character looks twisted, mirrored, flattened, offset, or skating in an animation.
- Need to decide whether an imported avatar/armature/retarget matches an expected pose.
- Need to decide whether a model is a character, prop, proxy mesh, control rig, or broken import before assigning blame.

## Workflow
1. **Inventory the scene.** List meshes, armatures, empties, cameras, lights, modifiers, parent relationships, hidden objects. Separate the character mesh from helper/proxy geometry BEFORE judging the avatar. Record object-space and world-space bounding boxes.
2. **Identify the skeleton.** Capture armature names, pose bones, bone heads/tails, roll, parent chains, constraints, rest-pose axes. Map semantic bones (hips, spine, neck, head, shoulders, elbows, hands, thighs, knees, ankles, feet). Flag missing left/right pairs and unusual naming.
3. **Determine forward / up / side axes.** Use pelvis + spine + shoulders + hips + head + feet together - never a single mesh normal. Compare local armature axes vs world axes vs the import convention (glTF Y-up vs Blender Z-up). Mark mirrored/backwards imports when face/head/feet direction conflicts with root motion.
4. **Sample the revealing frames.** Inspect first, middle, contact, airborne, and extreme frames. Record root location, root heading, pelvis height, torso lean, limb directions, foot clearance, mesh bounds. Sample more densely around flips, landings, turns, collisions, floor contacts.
5. **Check model integrity before blaming the retarget.** Confirm the clean baseline shape before applying animation. Preserve original mesh/materials/armature/skinning unless repair was explicitly requested. Treat sphere blobs, giant proxy meshes, or crushed bodies as import/selection issues until proven otherwise.
6. **Diagnose contact/motion issues:**
   - Ground penetration: lowest foot/shoe vertices vs floor height per frame.
   - Foot sliding: foot world positions across planted frames.
   - Leg crossover: left/right thigh-knee-ankle-foot side ordering.
   - Twist damage: bone swing direction SEPARATE from roll/twist around the limb axis.
   - Scale drift: animated mesh bounds vs the clean baseline bounds.
7. **Report facts before opinions.** Frame numbers, object names, bone names, world coords, thresholds. Separate confirmed failures from visual suspicions. Attach screenshots only after the structured state says what to look at.

## Report shape
```markdown
## Blender Motion Inspection
### Scene Inventory
- Character candidates / Armatures / Helper-proxy objects / Cameras-lights:
### Orientation
- World up / Character forward / Root heading / Mirrored-backwards risk:
### Baseline Integrity
- Clean mesh bounds / Animated mesh bounds / Materials-skin preserved / Suspicious non-character meshes:
### Frame Findings
| Frame | Finding | Evidence |
| --- | --- | --- |
| 1 | Clean baseline pose | hips/spine/feet aligned |
| 96 | Foot penetrates floor | left_foot min_z = -0.04 |
### Verdict
- Pass/fail / Required fix / Render readiness:
```

## Worked diagnoses
- **Walk cycle foot-sliding:** at planted frame 18 `foot.L min_z = 0.004` (planted), then `foot.L x = 0.21 -> 0.28` over six frames while `pelvis y = 1.14 -> 1.31`. Verdict: fail render-readiness - needs foot-lock cleanup / retarget constraint review; body mesh proportions are fine.
- **Backwards import:** frame 1 face vector (neck->head) resolves to world -Y, but `root y = 0.0 -> 2.8` (travels +Y) and toe bones point -Y against displacement. Verdict: backwards import / retarget forward-axis mismatch - fix the axis mapping before touching animation curves.

## Practical thresholds
- Assume Blender meter-scale units unless the scene unit scale says otherwise.
- Ground penetration above 1-2 cm is visible unless the floor is soft/stylized.
- Sudden scale change above 5% is a likely rig/constraint/transform-inheritance bug.
- Left/right ankle side-order flips during airborne inverted motion = leg-crossover risk even if it recovers.
- Root heading jumps above 30 deg/frame are suspicious unless the source has a snap turn.

## Anti-patterns
- Do not modify body proportions to force a pose match unless the task is explicit mesh repair.
- Do not bake away the clean baseline before recording it.
- Do not use one rendered camera angle as proof a pose is correct.
- Do not delete helper objects before recording why they are not the character.
- Do not assume facing direction without checking head + feet + torso + root motion together.

## Tooling note
Prefer a JSON state exporter (meshes, armatures, pose bones, materials, contacts, bounding boxes, sampled frames). If none exists, run a Blender Python script through Blender itself - `blender --background scene.blend --python collect_motion_state.py` - because `bpy` is not available in a normal system Python interpreter. Inside this employee, drive the same extraction through blender-mcp `execute_blender_code` (save the .blend first; see blender-backbone.md cautions).
