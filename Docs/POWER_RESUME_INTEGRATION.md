# COSMOS Power Resume integration design

Status: integration scaffold / engineering specification. Not yet enabled in the production image.

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
2. Build an opt-in COSMOS package or layer contribution. No new package should be added to CORE_IMAGE_EXTRA_INSTALL until resource and compatibility validation is complete.
3. Store state on persistent writable storage, not the read-only root filesystem or a volatile /tmp directory. Confirm mount semantics and durability on both Centauri Carbon hardware variants before selecting the final path.
4. Treat print progress as a journal. A single last-position record is not enough: use atomic write/rename, include version/schema, print file identity, file position, XYZ/E, speed/extrusion mode, active tool, temperatures, coordinate modes and a checksum. Bound write frequency to avoid flash wear.
5. Add logging to G-code through a non-invasive, deterministic preprocessing step or a Klipper-native mechanism. Never mutate the only original uploaded G-code file; write a separate prepared file and preserve original metadata. Reconcile byte offsets with the exact file Klipper is executing after Moonraker file processing.
6. Recovery generation must be a separate action and require a valid journal, matching original file identity, valid position within file size, and known extrusion/coordinate modes.
7. Do not auto-home blindly after power loss. COSMOS has homing_override and load-cell probing; any resume path must be specifically adapted to Centauri Carbon homing and validated on a test machine. Never move the gantry until the operator confirms the bed/toolhead are clear and the machine is in a safe state.
8. Heat up and move only after explicit operator confirmation. Check heaters, thermistors, fans, MCU connectivity, axes, toolhead, filament, bed mesh and compatible print file. Do not restore a stale chamber/extruder target without review.
9. Do not override COSMOS PRINT_START, PRINT_END, PAUSE, RESUME or CANCEL_PRINT blindly. They are substantial custom macros, including bed mesh, calibration, filament sensor, toolhead cleanup, fan state, skew and AFC behavior. Add a narrow recovery-specific entrypoint, and call shared routines only after exact behavior is verified.
10. Moonraker/Mainsail should expose state and operator actions, not run recovery logic itself. Keep the core implementation local to the Klipper configuration and small system helper.
11. Validate VIRTUAL_SDCARD in the installed Kalico version and the actual configured virtual_sdcard path. The upstream project requires VIRTUAL_SDCARD; this target repo has not yet been demonstrated to include it in an active printer config.
12. Test all failure paths: empty journal, partial journal write, missing file, file replaced/renamed, corrupted checksum, stale record, MCU disconnect, power loss, file end, print completion, cancel, pause, M600, runout, tool change/AFC and mesh/homing configuration.

## Proposed target layout (not committed yet)

- meta-opencentauri/recipes-apps/power-resume/power-resume_0.1.bb
- meta-opencentauri/recipes-apps/power-resume/files/power_resume.py (small helper / journal format)
- meta-opencentauri/recipes-apps/power-resume/files/power-resume.cfg (only opt-in macros)
- meta-opencentauri/recipes-apps/power-resume/files/power-resume-init-check.sh (optional startup validation; no long-running service)
- Documentation: Docs/POWER_RESUME.md

The recipe should install files into COSMOS-managed locations and rely only on available base tools/runtime already in the image. Avoid adding Python dependencies unless required.

## Integration gates before production

- Confirm mainboard persistent storage path and write endurance.
- Confirm VIRTUAL_SDCARD is enabled in actual machine config at runtime.
- Confirm how Kalico exposes file_position and whether file_position reliably identifies the next byte/command after restart.
- Confirm which process executes scripts, its UID, permissions and SELinux/AppArmor status (if any).
- Confirm COSMOS config generation preserves custom printer.cfg snippets.
- Confirm actual Centauri Carbon homing, mesh, offsets, fan, heater and AFC behaviors.
- Perform controlled power cuts only on a non-production test printer, with a fire-safe test setup.
- Build both supported hardware image targets and inspect package manifests, then test runtime behavior.

## Current delivery status

A feature branch was created for this work. This documentation is an engineering design only. No package, macro, runtime service or enabled image feature has been committed. No Yocto build or physical printer test has been run. Do not call the feature complete or safe to use until all gates pass.
