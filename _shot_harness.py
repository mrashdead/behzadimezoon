"""Harness موقت: رندر صفحهٔ لیست رزروها برای بررسی چشمی."""
import os
import re
import sys
from pathlib import Path

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

import django  # noqa: E402

django.setup()

from django.test import Client  # noqa: E402

from accounts.models import User  # noqa: E402

BASE_DIR = Path(__file__).resolve().parent
OUT_DIR = BASE_DIR / 'shots'
OUT_DIR.mkdir(exist_ok=True)

STATIC_DIR = Path('C:/Users/ash/Documents/Coding/behzadimezoon/static').as_uri()

LIGHT_BOOT = """
<script>
(function () {
  try {
    window.matchMedia = function (q) {
      return { matches: false, media: q, addListener: function(){}, removeListener: function(){}, addEventListener: function(){}, removeEventListener: function(){} };
    };
    window.localStorage.setItem('theme', 'light');
  } catch (e) {}
})();
</script>
<script>
document.addEventListener('DOMContentLoaded', function () {
  document.documentElement.setAttribute('data-bs-theme', 'light');
  document.body.setAttribute('data-bs-theme', 'light');
});
</script>
"""


def rewrite(html: str) -> str:
    html = html.replace('src="/static/', f'src="{STATIC_DIR}/')
    html = html.replace('href="/static/', f'href="{STATIC_DIR}/')
    html = re.sub(r'(<head[^>]*>)', r'\1' + LIGHT_BOOT, html, count=1)
    return html


def dump(client, url, name):
    response = client.get(url)
    body = response.content.decode('utf-8', errors='replace')
    (OUT_DIR / f'{name}.html').write_text(rewrite(body), encoding='utf-8')
    print(f'RESULT|{name}|{response.status_code}|{len(body)}')


def main():
    user = User.objects.filter(is_superuser=True).first()
    if user is None:
        print('RESULT|no-superuser')
        return 1

    client = Client()
    client.force_login(user)

    dump(client, '/reservations/', 'res_list')
    dump(client, '/reservations/?status=CONFIRMED', 'res_list_filtered')
    return 0


if __name__ == '__main__':
    sys.exit(main())
