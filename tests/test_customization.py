"""Branding overrides. Asserts the override mechanism, not the contents of the
bundled templates, so customising them doesn't break the suite.
"""

from fastapi.templating import Jinja2Templates

from app.main import template_directories


def render(name, custom_dir=None, **context):
    templates = Jinja2Templates(directory=template_directories(custom_dir))
    return templates.get_template(name).render(**context)


def test_custom_template_shadows_the_bundled_one(tmp_path):
    (tmp_path / "footer.html").write_text("CUSTOM FOOTER")

    assert render("footer.html", tmp_path).strip() == "CUSTOM FOOTER"


def test_bundled_template_is_used_when_the_custom_dir_omits_it(tmp_path):
    assert render("footer.html", tmp_path) == render("footer.html")


def test_missing_custom_dir_is_ignored(tmp_path):
    assert render("footer.html", tmp_path / "nope") == render("footer.html")


def test_logo_url_replaces_the_bundled_logo():
    page = render("base.html", url_for=lambda *a, **k: "", logo_url="/logo.svg")

    assert "/logo.svg" in page


def test_extra_css_is_linked_after_the_bundled_stylesheet():
    page = render(
        "base.html",
        url_for=lambda *a, **k: "/static/style.css",
        extra_css_url="/theme.css",
    )

    # Order matters: the deployment's rules have to win over the bundled ones.
    assert page.index("/theme.css") > page.index("/static/style.css")


def test_no_extra_stylesheet_is_linked_by_default():
    page = render("base.html", url_for=lambda *a, **k: "/static/style.css")

    assert page.count('<link rel="stylesheet"') == 1
