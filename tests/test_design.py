"""The screens follow the design in design/: the same icons, the same logo, the same red on the sidebar count, and the
refined Home, ID, care history and pop-up styles."""
import re
import unittest
from pathlib import Path

from gui.G_Icons import ICONS, LOGO, logo

ROOT = Path(__file__).resolve().parent.parent
DESIGN = ROOT / "design" / "html"


class TheIcons(unittest.TestCase):
    def test_every_icon_the_design_draws_is_in_the_app_exactly_as_drawn(self):
        drawn = set(ICONS.values()) | {LOGO}      # the logo is drawn like an icon but is not in the icon list
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


class TheRefinedStyles(unittest.TestCase):
    """The refinement pass: one gradient thread, a tile-less logo, five equal phone tabs, a dimmed and blurred pop-up."""

    def setUp(self):
        self.css = (ROOT / "gui" / "static" / "css" / "G_Style.css").read_text(encoding="utf-8")

    def rule(self, selector):
        """Everything the stylesheet says about one selector, later rules last (they win)."""
        return " ".join(re.findall(r"(?m)(?:^|\})\s*" + re.escape(selector) + r"\s*\{([^}]*)\}", self.css))

    def test_the_gradient_runs_through_the_sidebar_the_id_card_and_the_main_button(self):
        for selector in (".side", ".idcard", ".btn.primary"):
            self.assertRegex(self.rule(selector), r"gradient|--brand-grad|--shell-grad", selector)

    def test_the_logo_has_no_tile_behind_it(self):
        mark = self.rule(".logo-mark")
        self.assertNotRegex(mark, r"background\s*:\s*[^;]*(var\(--brand|gradient|#)")

    def test_the_phone_tab_bar_gives_all_five_slots_the_same_width(self):
        self.assertRegex(self.css, r"\.mtabs a\s*\{[^}]*flex:\s*1 1 0")

    def test_pop_ups_dim_the_page_by_38_percent_and_blur_it(self):
        backdrop = re.search(r"dialog\.sheet::backdrop\s*\{([^}]*)\}", self.css).group(1)
        self.assertIn("rgba(8,30,33,.38)", backdrop)
        self.assertIn("blur(8px)", backdrop)
        self.assertRegex(self.css, r"\.scrim\s*\{[^}]*blur\(8px\)")

    def test_the_qr_picture_is_a_white_220_pixel_square(self):
        qr = self.rule(".qrbox")
        self.assertIn("width:220px", qr)
        self.assertIn("background:#fff", qr)

    def test_the_date_of_birth_calendar_styles_are_still_there(self):
        self.assertIn(".date-wrap", self.css)
        self.assertIn("button.date-btn", self.css)


class TheSharedGrid(unittest.TestCase):
    """Profile and settings pieces, the one grid, and the toasts."""

    def setUp(self):
        self.css = (ROOT / "gui" / "static" / "css" / "G_Style.css").read_text(encoding="utf-8")
        self.clean = re.sub(r"/\*.*?\*/", "", self.css, flags=re.S)

    def test_the_braces_balance(self):
        self.assertEqual(self.clean.count("{"), self.clean.count("}"))

    def test_the_side_column_is_360_pixels_and_two_columns_start_at_1281_pixels(self):
        self.assertRegex(self.clean, r"\.grid\{[^}]*minmax\(0,1fr\) 360px")
        self.assertRegex(self.clean, r"@media \(max-width:1280px\) \{ \.grid \{ grid-template-columns:minmax\(0,1fr\); \} \}")
        wide = self.clean.split("@media (min-width:1281px){")[1].split("}\n.grid+.grid")[0]      # only this media block
        self.assertIn(".grid.half,.grid.pf{grid-template-columns:minmax(0,1fr) minmax(0,1fr)}", wide)
        self.assertNotIn("last-child", wide)                                 # no rule stretches the last panel of a column

    def test_every_toast_sits_bottom_centre_and_only_success_is_the_teal_pill(self):
        box = re.search(r"\.toasts \{([^}]*)\}", self.clean).group(1)
        self.assertIn("bottom:28px", box)
        self.assertIn("left:50%", box)
        self.assertNotIn("top:", box)
        self.assertIn("var(--brand-grad)", re.search(r"\.toast \{([^}]*)\}", self.clean).group(1))
        self.assertIn("var(--red-tint)", re.search(r"\.toast\.error \{([^}]*)\}", self.clean).group(1))
        self.assertIn("var(--amber-tint)", re.search(r"\.toast\.warning \{([^}]*)\}", self.clean).group(1))
        self.assertNotIn(".toasts { top:", self.clean)                       # the old top-right spot is gone

    def test_the_empty_state_row_is_scoped_and_the_plain_empty_is_left_alone(self):
        self.assertIn(".row.empty{display:flex", self.clean)
        self.assertNotRegex(self.clean, r"(?m)^\.empty\{[^}]*display:flex")
        self.assertIn(".empty{padding:28px var(--pad);color:var(--faint);text-align:center}", self.clean)

    def test_the_phone_tab_bar_is_flat_and_full_width(self):
        bar = re.search(r"\.mtabs\{display:flex;position:fixed;([^}]*)\}", self.clean).group(1)
        self.assertIn("left:0;right:0;bottom:0", bar)
        self.assertIn("border-radius:0", bar)
        self.assertNotIn("backdrop-filter", bar)

    def test_the_account_label_and_the_sidebar_arrow_have_no_styles_left_and_the_gear_shows_on_a_phone_only(self):
        self.assertNotIn("nav-label", self.clean)
        self.assertNotIn(".out", self.clean)
        self.assertNotIn(".ptabs", self.clean)                                   # the pill tabs were replaced by underline tabs
        self.assertIn(".top .gear{display:none}", self.clean)
        self.assertIn("@media (max-width:760px){.top .gear{display:grid}}", self.clean)

    def test_settings_panels_have_one_line_under_the_heading_and_none_between_rows(self):
        block = self.css.split("/* ---- Settings page")[1].split("*/", 1)[1].strip().splitlines()
        self.assertEqual(block[:7], [
            ".settings-page .panel .sec-h{padding-bottom:14px!important;border-bottom:1px solid var(--line)!important;margin-bottom:8px}",
            ".settings-page .set-row{min-height:64px;padding:12px 0;gap:16px;border:0}",
            ".settings-page .set-row .g small{margin-top:4px}",
            ".settings-page a.set-row,.settings-page a.set-row.link{margin:0!important;padding:12px 0!important}",
            ".settings-page>.panel{margin-top:24px}",
            ".settings-page .logout-panel{padding-top:4px!important;padding-bottom:4px!important;display:flex;align-items:center}",
            ".settings-page .logout-panel .act-row{min-height:56px}",
        ])
        self.assertIn(".panel>.sec-h,.panel>.card-h,.panel>.sec>.sec-h,.card>.card-h{padding-bottom:14px!important;border-bottom:1px solid var(--line)!important;margin-bottom:8px}", self.css)

    def test_panels_are_only_as_tall_as_their_content(self):
        self.assertIn(".grid{display:grid;grid-template-columns:minmax(0,1fr) 360px;gap:var(--gap);align-items:start}", self.css)
        self.assertNotIn("align-items:stretch", self.clean)
        self.assertNotIn("flex:1 1 auto", self.clean)
        lines = [line for line in self.css.rstrip().splitlines() if line]
        self.assertEqual(lines[-13:-10], [
            ".grid{align-items:start!important}",
            ".grid>.col>:last-child,.grid>.col>.panel{flex:0 0 auto!important}",
            ".grid>.panel,.grid>.card{align-self:start}",
        ])

    def test_the_end_of_the_stylesheet_has_the_designs_row_rules_in_order(self):
        lines = [line for line in self.css.rstrip().splitlines() if line]
        self.assertEqual(lines[-10:-3], [
            ".kvs .kv{align-items:flex-start!important;min-height:0!important;padding:12px 0!important;line-height:1.45}",
            ".kvs .kv>b{align-items:flex-start}",
            "@media(max-width:760px){.kvs .kv>span{width:104px!important}}",
            ".kvs .kv>span{font-weight:600!important;color:#12333A!important}",
            '.kvs .kv>span::after{content:":"}',
            ".kvs .kv>b{font-weight:400!important;color:#12333A}",
            ".panel .row,.panel .list>*,.panel .kv{border-top:0!important;border-bottom:0!important}",
        ])

    def test_allergy_and_severity_tags_are_soft_pills_and_moderate_is_amber(self):
        lines = [line for line in self.css.rstrip().splitlines() if line]
        self.assertEqual(lines[-3:], [
            ".atag{display:inline-flex;align-items:center;height:24px;padding:0 10px;margin:-2px 6px -2px 0;border-radius:999px;background:#FDECEA;color:#B42318!important;font-size:12.5px;font-weight:600;line-height:1}",
            ".atag:before{display:none}",
            ".atag.mod{background:#FEF3E2;color:#9A5B00!important}",
        ])

    def test_no_panel_has_a_line_between_its_sections_because_a_second_heading_is_its_own_panel(self):
        self.assertNotIn(".sec + .sec", self.css)

    def test_the_qr_code_sits_in_one_white_box_with_no_frame_of_its_own(self):
        box = re.search(r"\.qrbox \{([^}]*)\}", self.css).group(1)
        self.assertIn("box-shadow:inset 0 0 0 1px #E3ECEB", box)
        self.assertIn("background:#fff", box)
        self.assertIn("margin:18px auto", box)
        self.assertNotRegex(self.clean, r"(?m)^\.qr\{")                      # the drawing's own border and padding are gone
        self.assertNotIn("border:1px solid var(--line);border-radius:20px", self.clean)

    def test_text_greys_are_the_darker_readable_ones(self):
        self.assertIn("--muted:#4E676B; --faint:#5B7175;", self.clean)

    def test_important_is_only_used_where_it_must_win(self):
        """The merged styles replace the rules they supersede instead of out-shouting them."""
        block = self.css.split(".who{display:flex;align-items:center;gap:14px;padding:20px 0 8px}")[1].split("/* ---- Settings page")[0]
        used = [line.strip()[:70] for line in block.splitlines() if "!important" in line]
        self.assertEqual(len(used), 1, used)
        self.assertIn("prefers-reduced-motion", used[0])


class TheLoginBox(unittest.TestCase):
    """The login fields and the profile block in the sidebar are spaced and aligned like the design."""

    def setUp(self):
        self.css = (ROOT / "gui" / "static" / "css" / "G_Style.css").read_text(encoding="utf-8")

    def rule(self, selector):
        return re.search(re.escape(selector) + r" \{([^}]*)\}", self.css).group(1)

    def test_a_checkbox_does_not_inherit_the_text_boxes_padding(self):
        rule = self.rule("input[type=checkbox]")
        self.assertIn("padding:0", rule)
        self.assertIn("flex:none", rule)

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

    def test_the_sidebar_profile_block_has_balanced_space_and_no_arrow(self):
        self.assertIn("padding:12px 12px;display:flex;align-items:center", self.css)  # equal space above and below
        self.assertIn("flex:none", self.rule(".side-foot .avatar"))
        self.assertNotIn(".side-foot .out", self.css)


if __name__ == "__main__":
    unittest.main()
