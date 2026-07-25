from pathlib import Path

from django.test import SimpleTestCase


class TemplateScriptRefactorTests(SimpleTestCase):
    def read_template(self, template_name: str) -> str:
        return (Path(__file__).resolve().parents[2] / "templates" / template_name).read_text(encoding="utf-8")

    def test_base_template_exposes_extra_js_block(self) -> None:
        content = self.read_template("base.html")
        self.assertIn("{% block extra_js %}{% endblock %}", content)

    def test_customer_list_template_uses_external_script_include(self) -> None:
        content = self.read_template("customers/list.html")
        self.assertIn("{% include 'includes/scripts/customer_list_js.html' %}", content)
        self.assertNotIn("<script>", content)
