"""Load the final WorldWarDynasty core patches automatically with Python."""
import final_runtime_patch
import final_core_fix

# Promo/help/group callback handling is already installed by sitecustomize.py.
# Disable the extra run wrapper in final_runtime_patch.py so it cannot conflict
# with the existing callback ownership layer.
final_runtime_patch.patch_run = lambda run: None

# Global interceptor price override.
# Keep the price centralized through config.UNITS so shop, purchase prompts,
# purchase calculations and other UI that reads UNITS all use the same value.
try:
    import config
    config.UNITS['interceptor']['price'] = 9_000
except Exception as exc:
    print(f'[WorldWarDynasty] interceptor price patch warning: {exc}')
