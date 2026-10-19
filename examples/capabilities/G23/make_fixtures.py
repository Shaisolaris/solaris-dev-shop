#!/usr/bin/env python3
"""Writes the G23 fixtures. Every bundle is SYNTHETIC: written here for G23, not captured from a real
WordPress site. Plugin slugs (acme-*, shop-*) are invented. Deterministic: same output on every run."""
import json
import random
import sys
from pathlib import Path

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent / "fixtures"
SRC = "synthetic fixture written for G23; not captured from a real site"
ENV = {"php": "8.3.12", "wp": "6.6.2", "host": "synthetic-vm"}
MEAS = {"tool": "synthetic curl loop", "warm_cache": True, "runs_per_url": 7, "concurrency": 1}
GOOD_CFG = {"WP_DEBUG": False, "WP_DEBUG_LOG": True, "WP_DEBUG_DISPLAY": False, "WP_MEMORY_LIMIT": "256M", "WP_CACHE": True,
            "DISABLE_WP_CRON": True, "DB_PASSWORD": "synthetic-not-a-secret", "AUTH_KEY": "synthetic-not-a-key"}
PLUGINS = ["acme-seo/acme-seo.php", "acme-forms/acme-forms.php", "shop-core/shop-core.php", "shop-filters/shop-filters.php"]


def base(**kw):
    b = {"schema": "solaris.wp-trace/1", "site": "synthetic-shop", "environment": "production", "source": SRC, "env": ENV,
         "measurement": MEAS, "wp_config": dict(GOOD_CFG), "dropins": ["advanced-cache.php", "object-cache.php"],
         "active_plugins": PLUGINS, "autoload_bytes": 412000,
         "autoload_top": [{"option": "acme_seo_settings", "bytes": 61000}, {"option": "shop_core_options", "bytes": 40000}],
         "system_cron": True, "requests": [], "php_errors": [], "bisect": []}
    b.update(kw)
    return b


def queries(rng, page, n=4, slow=None, loop=0):
    qs = [{"sql": "SELECT option_value FROM wp_options WHERE option_name = 'siteurl' LIMIT 1", "ms": round(rng.uniform(0.2, 0.6), 3), "caller": "get_option", "component": "core"},
          {"sql": f"SELECT * FROM wp_posts WHERE post_name = '{page}' AND post_type = 'page'", "ms": round(rng.uniform(0.5, 2.0), 3), "caller": "WP_Query->get_posts", "component": "core"}]
    for i in range(n):
        qs.append({"sql": f"SELECT meta_key, meta_value FROM wp_postmeta WHERE post_id IN ({100 + i}, {200 + i})", "ms": round(rng.uniform(0.2, 1.5), 3),
                   "caller": "update_meta_cache", "component": "core"})
    for i in range(loop):
        qs.append({"sql": f"SELECT meta_value FROM wp_postmeta WHERE post_id = {500 + i} AND meta_key = '_price'", "ms": round(rng.uniform(0.3, 0.9), 3),
                   "caller": "Shop_Filters_Widget->render", "component": "plugin:shop-filters"})
    if slow:
        qs.append({"sql": "SELECT p.ID FROM wp_posts p JOIN wp_postmeta m ON m.post_id = p.ID WHERE m.meta_key = '_color' AND m.meta_value LIKE '%blue%' ORDER BY p.post_date DESC",
                   "ms": slow, "caller": "Shop_Filters_Query->run", "component": "plugin:shop-filters"})
    return qs


def hooks(rng, slow=False):
    h = [{"hook": "init", "callback": "Acme_SEO::init", "component": "plugin:acme-seo", "ms": round(rng.uniform(1, 4), 2)},
         {"hook": "wp_head", "callback": "acme_seo_meta", "component": "plugin:acme-seo", "ms": round(rng.uniform(0.5, 2), 2)}]
    if slow:
        h.append({"hook": "init", "callback": "Acme_Forms_Sync::remote_check", "component": "plugin:acme-forms", "ms": round(rng.uniform(250, 400), 1)})
    return h


def requests(rng, urls=("/", "/shop/", "/contact/"), runs=7, total=(80, 140), **kw):
    out = []
    for u in urls:
        for k in range(runs):
            page = u.strip("/") or "home"
            out.append({"id": f"{page}-{k + 1}", "url": u, "total_ms": round(rng.uniform(*total), 2), "peak_memory_mb": round(rng.uniform(48, 70), 1),
                        "queries": queries(rng, page, **kw), "hooks": hooks(rng)})
    return out


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rng = random.Random(23)
    fx = {}
    fx["01-clean-control"] = base(requests=requests(rng))
    conflict = base(requests=requests(rng, urls=("/contact/",), runs=2),
                    php_errors=["[18-Oct-2026 10:12:03 UTC] PHP Fatal error:  Cannot redeclare acme_sanitize_phone() (previously declared in /srv/www/wp-content/plugins/acme-seo/inc/helpers.php:41) in /srv/www/wp-content/plugins/acme-forms/includes/format.php on line 17"],
                    bisect=[{"plugins": ["acme-seo", "acme-forms", "shop-core", "shop-filters"], "result": "fail"},
                            {"plugins": ["acme-seo", "shop-core"], "result": "ok"},
                            {"plugins": ["acme-forms", "shop-filters"], "result": "ok"},
                            {"plugins": ["acme-seo", "acme-forms"], "result": "fail"},
                            {"plugins": ["acme-forms", "shop-core", "shop-filters"], "result": "ok"}])
    fx["02-plugin-conflict"] = conflict
    slowq = base(requests=requests(rng, urls=("/shop/",), slow=420.0, loop=40))
    fx["03-slow-and-repeated-query"] = slowq
    cfg = dict(GOOD_CFG, WP_DEBUG=True, WP_CACHE=True)
    del cfg["WP_DEBUG_DISPLAY"]
    fx["04-config-faults"] = base(wp_config=cfg, dropins=["object-cache.php"], system_cron=False, autoload_bytes=1650000,
                                  autoload_top=[{"option": "acme_seo_redirect_log", "bytes": 1180000}, {"option": "shop_core_options", "bytes": 40000}],
                                  requests=requests(rng, urls=("/",), runs=2))
    before = base(requests=requests(rng, urls=("/", "/shop/"), total=(300, 420), slow=260.0))
    after = base(requests=requests(rng, urls=("/", "/shop/"), total=(90, 150)))
    fx["05-before"] = before
    fx["06-after-same-measurements"] = after
    diff = base(measurement=dict(MEAS, warm_cache=False), requests=requests(rng, urls=("/", "/shop/"), runs=5, total=(60, 90)))
    fx["07-after-different-measurements"] = diff
    fx["08-bisect-ambiguous"] = base(requests=requests(rng, urls=("/",), runs=1),
                                     bisect=[{"plugins": ["acme-seo", "acme-forms", "shop-core", "shop-filters"], "result": "fail"},
                                             {"plugins": ["acme-seo", "shop-core"], "result": "ok"},
                                             {"plugins": ["acme-forms", "shop-filters"], "result": "ok"}])
    for name, b in fx.items():
        (OUT / f"{name}.json").write_text(json.dumps(b, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"{len(fx)} fixtures in {OUT}")


if __name__ == "__main__":
    main()
