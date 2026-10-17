"""The screens follow the design in design/: the same icons, the same logo, the same red on the sidebar count."""
import re
import unittest
from pathlib import Path

from gui.G_Icons import ICONS, LOGO, logo

ROOT = Path(__file__).resolve().parent.parent
DESIGN = ROOT / "design" / "html"


class TheIcons(unittest.TestCase):
    def test_every_icon_the_design_draws_is_in_the_app_exactly_as_drawn(self):
        drawn = set(ICONS.values())
        for page in sorted(DESIGN.glob("[0-9]*.html")):
            for inner in re.findall(r'<svg class="i[^"]*" viewBox="0 0 24 24">(.*?)</svg>', page.read_text(encoding="utf-8")):
                self.assertIn(inner, drawn, f"{page.name}: {inner[:60]}")

    def test_the_logo_is_the_pulse_scan_mark_drawn_like_the_other_icons(self):
        mark = str(logo())
        self.assertIn(LOGO, mark)
        self.assertIn("M7 12h2.5l1.5-3 2 6 1.5-3H17", mark)   # the heartbeat line
        self.assertIn('class="i ', mark)
        self.assertNotIn("logo-cross", mark)


class TheStylesheet(unittest.TestCase):
    def setUp(self):
        self.css = (ROOT / "gui" / "static" / "css" / "G_Style.css").read_text(encoding="utf-8")

    def test_the_sidebar_count_uses_the_designs_red_with_no_colour_of_its_own(self):
        self.assertIn("background:var(--red)", re.search(r"\.nav a \.count\{[^}]*\}", self.css).group(0))
        self.assertNotIn(".side .nav a .count", self.css)

    def test_the_bell_dot_is_the_designs_size(self):
        rule = re.search(r"\.ibtn \.badge \{([^}]*)\}", self.css).group(1)
        self.assertIn("top:9px; right:10px; width:8px; height:8px", rule)

    def test_the_old_filled_cross_logo_style_is_gone(self):
        self.assertNotIn("logo-cross", self.css)


class TheLoginBox(unittest.TestCase):
    """The login fields, the Remember me row and the profile block in the sidebar are spaced and aligned like the design."""

    def setUp(self):
        self.css = (ROOT / "gui" / "static" / "css" / "G_Style.css").read_text(encoding="utf-8")

    def rule(self, selector):
        return re.search(re.escape(selector) + r" \{([^}]*)\}", self.css).group(1)

    def test_a_checkbox_does_not_inherit_the_text_boxes_padding(self):
        rule = self.rule("input[type=checkbox]")
        self.assertIn("padding:0", rule)
        self.assertIn("flex:none", rule)

    def test_remember_me_has_room_above_the_button(self):
        self.assertRegex(self.rule(".check-line"), r"margin:2px 0 22px")

    def test_an_empty_message_line_takes_no_room_under_a_field(self):
        self.assertNotIn("min-height", self.rule(".field-foot"))
        self.assertIn(".field-foot:not(:has(", self.css)

    def test_the_text_inside_a_boxed_field_fills_the_box(self):
        self.assertIn("align-self:stretch", self.rule(".input input"))
        self.assertIn("cursor:text", self.rule(".input"))

    def test_the_browsers_saved_login_fill_does_not_paint_a_blue_patch(self):
        self.assertIn("input:-webkit-autofill", self.css)
        self.assertRegex(self.css, r"-webkit-autofill[^}]*box-shadow:0 0 0 1000px var\(--surface\) inset")

    def test_typed_text_and_the_caret_use_the_browsers_normal_colours(self):
        rule = self.rule(".input input")
        self.assertIn("color:FieldText", rule)
        self.assertIn("caret-color:auto", rule)
        self.assertNotIn("var(--brand)", rule)
        self.assertNotIn("var(--ink)", rule)

    def test_the_icons_are_on_the_right_items(self):
        # each name draws its own shape (an earlier mix-up put a key on the QR button and a check on My Record)
        shapes = {"qr": '<rect x="3" y="3" width="7" height="7"/>', "key": '<circle cx="8" cy="15" r="4"/>', "file": '<path d="M14 3H6a1 1',
                  "shieldok": 'm9 12 2 2 4-4', "history": 'M3 12a9 9 0 1 0 3-6.7L3 8', "user": '<circle cx="12" cy="8" r="4"/>',
                  "check": '<path d="m5 12 5 5 9-10"/>', "x": '<path d="M6 6l12 12M18 6 6 18"/>', "eye": '<circle cx="12" cy="12" r="3"/>',
                  "home": 'M3 10.5 12 3l9 7.5', "bell": 'M6 8a6 6 0 0 1 12', "logout": 'M15 4h4a1 1', "chev": '<path d="m9 5 7 7-7 7"/>'}
        for name, shape in shapes.items():
            self.assertIn(shape, ICONS[name], name)

    def test_the_login_button_sits_below_the_last_field(self):
        self.assertIn("margin-top:8px", self.rule(".auth-form form .btn.block"))

    def test_the_sidebar_profile_block_has_balanced_space_and_a_steady_chevron(self):
        self.assertIn("padding:12px 12px;display:flex;align-items:center", self.css)  # equal space above and below
        self.assertIn("flex:none", self.rule(".side-foot .avatar, .side-foot .out"))


if __name__ == "__main__":
    unittest.main()
