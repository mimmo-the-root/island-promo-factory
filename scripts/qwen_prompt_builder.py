import sys as _sys; from pathlib import Path as _P; _sys.path.insert(0, str(_P(__file__).resolve().parent))  # embedded python ignores script dir
from pathlib import Path
import json


# ============================================================
# ISLAND PROMO FACTORY
# Qwen Prompt Builder
# Version 0.1
#
# Reads:
#   Projects/<project>/config.json
#   Projects/<project>/qwen_prompt.txt
#
# Produces:
#   Projects/<project>/qwen_prompt_final.txt
#
# This script DOES NOT communicate with ComfyUI.
# It only builds the final prompt.
# ============================================================


# ------------------------------------------------------------
# PATHS
# ------------------------------------------------------------

PROMO_FACTORY_DIR = Path(__file__).resolve().parent.parent

import promo_project  # noqa: E402

PROJECT_DIR = promo_project.project_dir()

CONFIG_JSON = (
    PROJECT_DIR
    / "config.json"
)

PROMPT_TEMPLATE = promo_project.prompt_path("qwen_prompt_horizontal.txt")

OUTPUT_PROMPT = (
    PROJECT_DIR
    / "qwen_prompt_final.txt"
)


# ------------------------------------------------------------
# HELPERS
# ------------------------------------------------------------

def load_config():
    if not CONFIG_JSON.exists():
        raise FileNotFoundError(
            f"Config not found:\n{CONFIG_JSON}"
        )

    with open(
        CONFIG_JSON,
        "r",
        encoding="utf-8"
    ) as f:
        return json.load(f)


def load_prompt_template():
    if not PROMPT_TEMPLATE.exists():
        raise FileNotFoundError(
            f"Prompt template not found:\n"
            f"{PROMPT_TEMPLATE}"
        )

    with open(
        PROMPT_TEMPLATE,
        "r",
        encoding="utf-8"
    ) as f:
        return f.read()


def build_character_section(characters):
    """
    Creates a readable character configuration section
    that can be appended to the Qwen prompt.
    """

    lines = []

    lines.append(
        "CHARACTER CONFIGURATION:"
    )

    lines.append(
        ""
    )

    for index, character in enumerate(
        characters,
        start=1
    ):

        file_path = character.get(
            "file",
            f"character_{index:02d}.png"
        )

        side = character.get(
            "side",
            "center"
        )

        pose = character.get(
            "pose",
            "dynamic combat-ready pose"
        )

        facing = character.get(
            "facing",
            "center"
        )

        lines.append(
            f"CHARACTER {index:02d}:"
        )

        lines.append(
            f"- source: {file_path}"
        )

        identity = character.get("identity")
        if identity:
            lines.append(
                f"- identity (must be preserved exactly): {identity}"
            )

        lines.append(
            f"- position: {side}"
        )

        lines.append(
            f"- pose: {pose}"
        )

        lines.append(
            f"- facing: {facing}"
        )

        lines.append(
            ""
        )

    return "\n".join(lines)


def build_qwen_prompt(config, template):
    """
    Combines the static prompt template with the dynamic
    character configuration from config.json.
    """

    characters = config.get(
        "characters",
        []
    )

    if not characters:
        raise ValueError(
            "No characters found in config.json."
        )

    character_section = build_character_section(
        characters
    )

    final_prompt = (
        template.rstrip()
        + "\n\n"
        + character_section
    )

    # Optional per-map control in config.json:
    #   "prompt": {"extra": "free instructions", "avoid": "things Qwen must not add"}
    extra = config.get("prompt", {})
    if extra.get("extra"):
        final_prompt += "\n\nEXTRA INSTRUCTIONS:\n" + str(extra["extra"]).strip()
    if extra.get("avoid"):
        final_prompt += "\n\nALSO DO NOT ADD: " + str(extra["avoid"]).strip()

    return final_prompt


# ------------------------------------------------------------
# MAIN
# ------------------------------------------------------------

def main():

    print("=" * 60)
    print("ISLAND PROMO FACTORY")
    print("Qwen Prompt Builder v0.1")
    print("=" * 60)

    # --------------------------------------------------------
    # Load
    # --------------------------------------------------------

    custom = PROJECT_DIR / "qwen_prompt_custom.txt"
    if custom.exists():
        # a hand-edited prompt wins over the template; delete the file to go back to the automatic one
        OUTPUT_PROMPT.write_text(custom.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"Using your hand-edited prompt: {custom.name} (delete it to use the automatic prompt)")
        return

    config = load_config()

    template = load_prompt_template()

    # --------------------------------------------------------
    # Build
    # --------------------------------------------------------

    final_prompt = build_qwen_prompt(
        config,
        template
    )

    # --------------------------------------------------------
    # Save
    # --------------------------------------------------------

    with open(
        OUTPUT_PROMPT,
        "w",
        encoding="utf-8"
    ) as f:

        f.write(
            final_prompt
        )

    # --------------------------------------------------------
    # Report
    # --------------------------------------------------------

    characters = config.get(
        "characters",
        []
    )

    print()
    print(
        f"Characters: {len(characters)}"
    )

    print(
        f"Template: {PROMPT_TEMPLATE}"
    )

    print(
        f"Output: {OUTPUT_PROMPT}"
    )

    print()
    print("=" * 60)
    print("DONE")
    print("=" * 60)


if __name__ == "__main__":
    main()