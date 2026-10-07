"""Light and dark tokens stay readable, and both surfaces follow the OS theme."""

from __future__ import annotations

import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _channel(value: int) -> float:
    channel = value / 255
    if channel <= 0.04045:
        return channel / 12.92
    return ((channel + 0.055) / 1.055) ** 2.4


def _luminance(hex_color: str) -> float:
    raw = hex_color.lstrip("#")
    red = int(raw[0:2], 16)
    green = int(raw[2:4], 16)
    blue = int(raw[4:6], 16)
    return 0.2126 * _channel(red) + 0.7152 * _channel(green) + 0.0722 * _channel(blue)


def contrast_ratio(foreground: str, background: str) -> float:
    lighter = max(_luminance(foreground), _luminance(background))
    darker = min(_luminance(foreground), _luminance(background))
    return (lighter + 0.05) / (darker + 0.05)


class ThemeContrastTests(unittest.TestCase):
    def test_text_pairs_meet_wcag_aa(self) -> None:
        from execution.design_tokens import load_design_tokens

        load_design_tokens.cache_clear()
        tokens = load_design_tokens()
        for theme in ("light", "dark"):
            palette = tokens[theme]
            for name in ("text", "textMute", "textDim", "accent"):
                ratio = contrast_ratio(palette[name], palette["bg"])
                self.assertGreaterEqual(ratio, 4.5, f"{theme} {name} on bg is {ratio:.2f}")
            button = contrast_ratio(palette["accentInk"], palette["accent"])
            self.assertGreaterEqual(button, 4.5, f"{theme} accent ink is {button:.2f}")
            self.assertNotIn(palette["bg"].lower(), {"#fff", "#ffffff", "#000", "#000000"})
            self.assertNotIn(palette["text"].lower(), {"#fff", "#ffffff", "#000", "#000000"})

    def test_site_and_email_follow_color_scheme(self) -> None:
        css = (REPO_ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")
        index = (REPO_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
        renderer = (REPO_ROOT / "emails" / "render_email.mjs").read_text(encoding="utf-8")
        self.assertIn("prefers-color-scheme: dark", css)
        self.assertIn('name="color-scheme" content="light dark"', index)
        self.assertIn("prefers-color-scheme: dark", renderer)
        self.assertIn("[data-ogsc]", renderer)
        self.assertIn("[data-ogsb]", renderer)
        self.assertIn("tokens.light", renderer)

    def test_archive_css_switches_with_the_os(self) -> None:
        from execution.design_tokens import archive_root_css, load_design_tokens

        load_design_tokens.cache_clear()
        css = archive_root_css()
        tokens = load_design_tokens()
        self.assertIn(tokens["light"]["bg"], css)
        self.assertIn("prefers-color-scheme: dark", css)
        self.assertIn(tokens["dark"]["bg"], css.split("prefers-color-scheme")[1])


if __name__ == "__main__":
    unittest.main()
