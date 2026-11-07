# COSMOS firmware update — Power Resume + Mainsail V4

## Included changes

### Native Power Resume checkpoint journal
- Adds the optional Kalico `power_resume` module.
- Stores a checksummed, atomically replaced checkpoint under `/user-resource/power-resume/state.json`.
- Adds `POWER_RESUME_STATUS`, `POWER_RESUME_CHECK`, `POWER_RESUME_SAVE` and `POWER_RESUME_CLEAR`.
- Connects checkpoint save/clear to the existing print lifecycle macros.
- Disabled by default on both Centauri Carbon machine profiles. This is checkpoint recording and validation only; it does not yet perform automatic print recovery or motion.

### COSMOS Mainsail V4 theme
- Adds the text-free starfield wallpaper and dark glass / 3D CSS theme.
- Installs `custom.css` and `cosmos-starfield.svg` automatically into `/etc/klipper/config/.theme/` through the Mainsail Yocto recipe.
- Keeps the existing `default.json` interface configuration and macro groups intact.
- Uses the firmware's actual configuration path rather than the generic Raspberry Pi `~/printer_data/config/.theme` path.

## Build and validation status

The GitHub pull-request workflow is configured to build both `centauri-carbon-1` and `centauri-carbon-2`. The integration must still pass that Yocto build and be tested on both physical printer variants before it is considered a production firmware update.

The Power Resume module is deliberately opt-in. A successful image build does not, by itself, validate power-loss recovery. Full recovery generation, safe homing/position restoration, and controlled power-cut tests remain separate work.
