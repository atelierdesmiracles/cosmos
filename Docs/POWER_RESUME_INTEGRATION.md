# COSMOS Power Resume integration design

Status: first implementation committed on an isolated feature branch. Package is included in the image recipe but checkpointing is disabled by default. No Yocto build or physical printer test has been run. A draft pull request has been opened to invoke the repository's dual-machine build workflow.

## Goal

Port the recovery workflow from T9Air/Klipper_Power_Resume to the Yocto-based COSMOS firmware without importing its Raspberry Pi/KIAUH installer or its assumptions about /home/<user>/printer_data.

Upstream project: https://github.com/T9Air/Klipper_Power_Resume
Upstream version observed in README: 3.6.0.beta.1
Upstream license: GPL-3.0
Target: https://github.com/atelierdesmiracles/cosmos

## Findings from target firmware

- COSMOS is a Yocto image for Elegoo Centauri Carbon and uses Kalico.
- Kalico config is installed under /etc/klipper/config.
- The default user G-code storage is linked by Moonraker to /user-resource/gcodes.
- Moonraker has a read-only configuration directory and Klipper has klipper-readonly config files.
- Klipper is started by SysV init; config is assembled by build-klipper-var-config.
- The base COSMOS README explicitly warns that the stock mainboard has very little spare CPU/RAM and discourages extra plugins.
- The upstream Power Resume install guide expects a Raspberry Pi, KIAUH and gcode_shell_command. It requires VIRTUAL_SDCARD.
- The upstream macros use scripts under /home/USER/Klipper_Power_Resume and a printer_data/config path, which is not the COSMOS layout.
- The upstream README currently labels the version 3.6.0.beta.1. Do not assume all scripts are stable.
- Upstream kpr-config/log.sh and finished.sh show a suspicious shell assignment with spaces around '=' (for example 'printer_path = ...'), which is not valid Bash syntax. The CREATE_FILE macro also references the add_logs command where the create_file command appears intended. Port logic must fix such defects and tests should cover it rather than transplant blindly.

## Integration strategy

1. Do not import KIAUH, the T9Air interactive installer, a permanent daemon, or gcode_shell_command solely to support recovery.
2. Package the module as an opt-in COSMOS component. It is included in the image, but its timer and journal writes remain disabled by default until persistent storage and runtime behavior are verified.
3. Store state on persistent writable storage, not the read-only root filesystem or a volatile /tmp directory. Confirm mount semantics and durability on both Centauri Carbon hardware variants before selecting the final path.
4. Treat print progress as a journal. A single last-position record is not enough: use atomic write/rename, include version/schema, print file identity, file position, XYZ/E, speed/extrusion mode, temperatures, coordinate modes and a checksum. Active tool/AFC state remains to be added. Bound write frequency to avoid flash wear.
5. Add logging to G-code through a non-invasive, deterministic preprocessing step or a Klipper-native mechanism. Never mutate the only original uploaded G-code file; write a separate prepared file and preserve original metadata. Reconcile byte offsets with the exact file Klipper is executing after Moonraker file processing.
6. Recovery generation must be a separate action and require a valid journal, matching original file identity, valid position within file size, and known extrusion/coordinate modes.
7. Do not auto-home blindly after power loss. COSMOS has homing_override and load-cell probing; any resume path must be specifically adapted to Centauri Carbon homing and validated on a test machine. Never move the gantry until the operator confirms the bed/toolhead are clear and the machine is in a safe state.
8. Heat up and move only after explicit operator confirmation. Check heaters, thermistors, fans, MCU connectivity, axes, toolhead, filament, bed mesh and compatible print file. Do not restore a stale chamber/extruder target without review.
9. Do not override COSMOS PRINT_START, PRINT_END, PAUSE, RESUME or CANCEL_PRINT blindly. They are substantial custom macros, including bed mesh, calibration, filament sensor, toolhead cleanup, fan state, skew and AFC behavior. Add a narrow recovery-specific entrypoint, and call shared routines only after exact behavior is verified.
10. Moonraker/Mainsail should expose state and operator actions, not run recovery logic itself. Keep the core implementation local to the Klipper configuration and small system helper.
11. The target machine configs for both Centauri Carbon variants include `[virtual_sdcard]` with path `/etc/klipper/gcodes`. The module reads the live `virtual_sdcard.get_status()` API. Verify the symlink/mount resolves to persistent storage on each installed image.
12. Test all failure paths: empty journal, partial journal write, missing file, file replaced/renamed, corrupted checksum, stale record, MCU disconnect, power loss, file end, print completion, cancel, pause, M600, runout, tool change/AFC and mesh/homing configuration.

## Implemented in the feature branch

- Added a native Kalico extra module at `meta-opencentauri/recipes-apps/power-resume/files/power_resume.py`.
- Added an optional Yocto recipe `power-resume_0.1.bb` and included the package in `cosmos-image-base.bb`.
- Added `power_resume_enabled = False` to both Centauri Carbon machine defaults and a matching validator in `config_manager.py`.
- Extended `build-klipper-var-config.sh` to generate the `[power_resume]` section at startup.
- Added `POWER_RESUME_CLEAR` at print start and print end so a previous print checkpoint is not offered after a new job or a normal end/cancel.
- Added native G-code commands: `POWER_RESUME_STATUS`, `POWER_RESUME_CHECK`, `POWER_RESUME_SAVE`, and `POWER_RESUME_CLEAR`.
- The existing COSMOS `PAUSE` macro requests an immediate checkpoint before its parking/retraction sequence.
- The module records file path, file identity metadata, byte offset, G-code position, coordinate/extrusion modes, speed factors and heater targets. Writes use a checksum, temporary file, atomic rename and fsync.
- The module is disabled by default and does not home, heat, move, generate a restarted G-code file or resume automatically.

## Remaining implementation scope

- Generate a recovery G-code artifact from a validated checkpoint without modifying the original upload.
- Implement a Centauri-specific, operator-confirmed homing and safe-position procedure.
- Reconcile file offsets, G-code parser state, extrusion mode, offsets, mesh, AFC/tool selection and slicer start/end behavior.
- Expose recovery review and confirmation in Mainsail/COSMOS UI.
- Add automated unit tests and complete Yocto builds for both hardware variants.

## How to enable checkpointing for bench testing

Set `power_resume_enabled = True` in `/etc/klipper/config/cosmos.conf`, then reboot the printer. This setting is not yet exposed as a polished Mainsail control. Checkpointing is disabled by default. Confirm that `/user-resource` is persistent on the exact hardware/image before enabling it.

With Klipper connected, use:

- `POWER_RESUME_STATUS` — report whether a checkpoint exists.
- `POWER_RESUME_CHECK` — validate the journal and unchanged source G-code file. This does not resume.
- `POWER_RESUME_SAVE` — force a checkpoint while a virtual SD file is loaded (also called by the COSMOS pause macro).
- `POWER_RESUME_CLEAR` — delete the checkpoint.

## Integration gates before production

- Confirm mainboard persistent storage path and write endurance.
- Confirm VIRTUAL_SDCARD is enabled in actual machine config at runtime.
- Confirmed in the current Kalico `virtual_sdcard.py`: status exposes `file_path`, `is_active`, and `file_position`; the implementation now reads these via `get_status()`. Still verify the behavior on the exact COSMOS pinned Kalico commit and a physical print.
- Confirm which process executes scripts, its UID, permissions and SELinux/AppArmor status (if any).
- Confirm COSMOS config generation preserves custom printer.cfg snippets.
- Confirm actual Centauri Carbon homing, mesh, offsets, fan, heater and AFC behaviors.
- Perform controlled power cuts only on a non-production test printer, with a fire-safe test setup.
- Build both supported hardware image targets and inspect package manifests, then test runtime behavior.

## Current delivery status

The package, plugin, settings plumbing and limited macro hooks are committed to the feature branch and proposed in draft PR #2. Checkpointing remains disabled by default. No Yocto build or physical printer test has been run. This is not yet a full print-resume implementation and must not be represented as one until recovery-file generation, safe homing/motion strategy and bench tests are complete.
