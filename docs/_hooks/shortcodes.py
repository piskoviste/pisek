# Edited version of https://github.com/squidfunk/mkdocs-material/blob/master/src/overrides/hooks/shortcodes.py

from __future__ import annotations

import re

from mkdocs.config.defaults import MkDocsConfig
from mkdocs.structure.files import Files
from mkdocs.structure.pages import Page
from re import Match

# -----------------------------------------------------------------------------
# Hooks
# -----------------------------------------------------------------------------


# @todo
def on_page_markdown(markdown: str, *, page: Page, config: MkDocsConfig, files: Files):

    # Replace callback
    def replace(match: Match):
        type, args = match.groups()
        args = args.strip()
        if type == "version":
            return _badge_for_version(args)
        elif type == "flag":
            return flag(args)
        elif type == "type":
            return _badge_for_type(args)

        elif type == "default":
            return _badge_for_default(args)
        elif type == "default-empty":
            return _badge_for_default_empty()

        # Otherwise, raise an error
        raise RuntimeError(f"Unknown shortcode: {type}")

    # Find and replace all external asset URLs in current page
    return re.sub(r"<!-- md:([\w-]+)(.*?) -->", replace, markdown, flags=re.I | re.M)


# -----------------------------------------------------------------------------
# Helper functions
# -----------------------------------------------------------------------------


# Create a flag of a specific type
def flag(args: str):
    type, *_ = args.split(" ", 1)
    if type == "experimental":
        return _badge_for_experimental()
    elif type == "required":
        return _badge_for_required()
    elif type == "required-applicable":
        return _badge_for_required_applicable()
    elif type == "customization":
        return _badge_for_customization()
    raise RuntimeError(f"Unknown type: {type}")


# -----------------------------------------------------------------------------


# Create badge
def _badge(icon: str, text: str = "", type: str = ""):
    classes = f"mdx-badge mdx-badge--{type}" if type else "mdx-badge"
    return "".join(
        [
            f'<span class="{classes}">',
            *([f'<span class="mdx-badge__icon">{icon}</span>'] if icon else []),
            *([f'<span class="mdx-badge__text">{text}</span>'] if text else []),
            f"</span>",
        ]
    )


# Create badge for version
def _badge_for_version(text: str):
    icon = "material-tag-outline"
    return _badge(
        icon=f":{icon}:{{ title='Minimum version' }}",
        text=(
            f"[{text}](https://github.com/piskoviste/pisek/releases/tag/v{text})"
            if text
            else ""
        ),
    )


# Create badge for type
def _badge_for_type(text: str):
    icon = "fontawesome-solid-triangle-circle-square"
    return _badge(
        icon=f":{icon}:{{ title='Type' }}",
        text=(f"[{text}](#value-types)" if text else ""),
    )


# Create badge for default value
def _badge_for_default(text: str):
    icon = "material-water"
    return _badge(icon=f":{icon}:{{ title='Default value' }}", text=text)


# Create badge for empty default value
def _badge_for_default_empty():
    icon = "material-water-outline"
    return _badge(icon=f":{icon}:{{ title='Default value is empty' }}")


# Create badge for required value flag
def _badge_for_required():
    icon = "material-alert"
    return _badge(icon=f":{icon}:{{ title='Required value' }}")


# Create badge for required value flag
def _badge_for_required_applicable():
    icon = "material-alert-plus"
    return _badge(icon=f":{icon}:{{ title='Required value if applicable' }}")


# Create badge for customization flag
def _badge_for_customization():
    icon = "material-brush-variant"
    return _badge(icon=f":{icon}:{{ title='Customization' }}")


# Create badge for experimental flag
def _badge_for_experimental():
    icon = "material-flask-outline"
    return _badge(icon=f":{icon}:{{ title='Experimental' }}")
