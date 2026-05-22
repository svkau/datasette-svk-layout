import json
from datetime import datetime
from datasette.utils.asgi import Response, Forbidden


def _get_metadata_db():
    from datasette_svk_layout import _get_metadata_db as get_db
    return get_db()


async def _check_admin(datasette, request):
    """Check if current actor has access.search_admin permission."""
    actor = request.actor if hasattr(request, 'actor') else None
    if actor is None:
        return False
    actor_permissions = actor.get('permissions', [])
    return 'access.search_admin' in actor_permissions


async def _render(datasette, request, template, context):
    """Render a template with admin context."""
    body = await datasette.render_template(template, context, request=request)
    return Response.html(body)


async def admin_databases(scope, receive, datasette, request):
    """List all databases in the metadata store."""
    if not await _check_admin(datasette, request):
        raise Forbidden("Administratorsbehörighet krävs")

    mdb = _get_metadata_db()
    search = request.args.get("search", "")
    db_type = request.args.get("type", "")

    databases = mdb.list_databases(
        search=search or None,
        db_type=db_type or None,
    )

    # Add permission info to each database
    for db in databases:
        perms = mdb.get_database_permissions(db["database_name"])
        db["permissions"] = perms

    return await _render(datasette, request, "admin_databases.html", {
        "databases": databases,
        "search": search,
        "db_type": db_type,
    })


async def admin_database_edit(scope, receive, datasette, request):
    """Edit metadata and permissions for a single database."""
    if not await _check_admin(datasette, request):
        raise Forbidden("Administratorsbehörighet krävs")

    mdb = _get_metadata_db()
    database_name = request.url_vars["database_name"]

    if request.method == "POST":
        post_vars = await request.post_vars()

        # Save metadata
        mdb.set_database_metadata(
            database_name,
            title=post_vars.get("title") or None,
            description=post_vars.get("description") or None,
            source=post_vars.get("source") or None,
            license=post_vars.get("license") or None,
        )

        # Save permissions for each action
        # view-database: organizations_ids
        org_ids_str = post_vars.get("perm_view-database_organizations_ids", "").strip()
        if org_ids_str:
            org_ids = [v.strip() for v in org_ids_str.split(",") if v.strip()]
            mdb.set_database_permissions(database_name, "view-database", {"organizations_ids": org_ids})
        else:
            mdb.set_database_permissions(database_name, "view-database", None)

        # execute-sql: permissions
        perms_str = post_vars.get("perm_execute-sql_permissions", "").strip()
        if perms_str:
            perms = [p.strip() for p in perms_str.split(",") if p.strip()]
            mdb.set_database_permissions(database_name, "execute-sql", {"permissions": perms})
        else:
            mdb.set_database_permissions(database_name, "execute-sql", None)

        return Response.redirect(f"/-/admin/databases/{database_name}?saved=1")

    # GET: load current values
    metadata = mdb.get_database_metadata(database_name) or {}
    permissions = mdb.get_database_permissions(database_name)
    saved = request.args.get("saved", "")

    return await _render(datasette, request, "admin_database_edit.html", {
        "database_name": database_name,
        "metadata": metadata,
        "permissions": permissions,
        "saved": saved,
        "is_new": not metadata,
    })


async def admin_database_delete(scope, receive, datasette, request):
    """Delete a database entry from the metadata store."""
    if not await _check_admin(datasette, request):
        raise Forbidden("Administratorsbehörighet krävs")

    if request.method != "POST":
        return Response.text("Method not allowed", status=405)

    mdb = _get_metadata_db()
    database_name = request.url_vars["database_name"]
    mdb.delete_database(database_name)
    return Response.redirect("/-/admin/databases?deleted=1")


async def admin_import(scope, receive, datasette, request):
    """Import database-level metadata from metadata.json."""
    if not await _check_admin(datasette, request):
        raise Forbidden("Administratorsbehörighet krävs")

    mdb = _get_metadata_db()
    result = None
    preview = None
    error = None

    if request.method == "POST":
        post_vars = await request.post_vars()
        action = post_vars.get("action", "preview")

        metadata_json = datasette._metadata_local
        if not metadata_json:
            error = "Ingen metadata.json hittades."
        elif action == "preview":
            # Show what would be imported
            databases = metadata_json.get("databases", {})
            preview = []
            for db_name, db_config in sorted(databases.items()):
                entry = {"name": db_name}
                entry["title"] = db_config.get("title", "")
                entry["description"] = db_config.get("description", "")
                entry["has_allow"] = "allow" in db_config
                entry["has_allow_sql"] = "allow_sql" in db_config
                preview.append(entry)
        elif action == "import":
            result = mdb.import_from_metadata_json(metadata_json)
    else:
        # GET: show info about what can be imported
        metadata_json = datasette._metadata_local
        if metadata_json:
            db_count = len(metadata_json.get("databases", {}))
        else:
            db_count = 0

    return await _render(datasette, request, "admin_import.html", {
        "result": result,
        "preview": preview,
        "error": error,
        "db_count": db_count if request.method == "GET" else None,
    })


def _get_actor_name(request):
    actor = request.actor if hasattr(request, 'actor') else None
    if not actor:
        return "Okänd"
    first = actor.get("first_name", "")
    last = actor.get("last_name", "")
    return f"{first} {last}".strip() or actor.get("username", "Okänd")


async def admin_site(scope, receive, datasette, request):
    """Edit site content (about text) and quick links."""
    if not await _check_admin(datasette, request):
        raise Forbidden("Administratorsbehörighet krävs")

    mdb = _get_metadata_db()

    if request.method == "POST":
        post_vars = await request.post_vars()

        # Save about content
        mdb.set_site_content("about_title", post_vars.get("about_title", "").strip())
        mdb.set_site_content("about_html", post_vars.get("about_html", "").strip())

        # Save links
        links = []
        i = 0
        while True:
            title = post_vars.get(f"link_title_{i}", "").strip()
            url = post_vars.get(f"link_url_{i}", "").strip()
            if not title and not url:
                break
            if title and url:
                links.append({"title": title, "url": url, "sort_order": i})
            i += 1
        mdb.set_site_links(links)

        return Response.redirect("/-/admin/site?saved=1")

    # GET
    about_title = mdb.get_site_content("about_title", "")
    about_html = mdb.get_site_content("about_html", "")
    links = mdb.get_site_links()
    saved = request.args.get("saved", "")

    return await _render(datasette, request, "admin_site.html", {
        "about_title": about_title,
        "about_html": about_html,
        "links": links,
        "saved": saved,
    })


async def admin_news_list(scope, receive, datasette, request):
    """List all news items."""
    if not await _check_admin(datasette, request):
        raise Forbidden("Administratorsbehörighet krävs")

    mdb = _get_metadata_db()
    news = mdb.get_site_news(limit=100)
    deleted = request.args.get("deleted", "")

    return await _render(datasette, request, "admin_news_list.html", {
        "news": news,
        "deleted": deleted,
    })


async def admin_news_new(scope, receive, datasette, request):
    """Create a new news item."""
    if not await _check_admin(datasette, request):
        raise Forbidden("Administratorsbehörighet krävs")

    mdb = _get_metadata_db()

    if request.method == "POST":
        post_vars = await request.post_vars()
        title = post_vars.get("title", "").strip()
        body = post_vars.get("body", "").strip()
        author = _get_actor_name(request)

        if title and body:
            news_id = mdb.add_news(title, body, author)
            return Response.redirect(f"/-/admin/news/{news_id}?saved=1")

    return await _render(datasette, request, "admin_news_edit.html", {
        "news": None,
        "is_new": True,
        "author_name": _get_actor_name(request),
    })


async def admin_news_edit(scope, receive, datasette, request):
    """Edit an existing news item."""
    if not await _check_admin(datasette, request):
        raise Forbidden("Administratorsbehörighet krävs")

    mdb = _get_metadata_db()
    news_id = int(request.url_vars["news_id"])

    if request.method == "POST":
        post_vars = await request.post_vars()
        title = post_vars.get("title", "").strip()
        body = post_vars.get("body", "").strip()
        author = _get_actor_name(request)

        if title and body:
            mdb.update_news(news_id, title, body, author)
            return Response.redirect(f"/-/admin/news/{news_id}?saved=1")

    news = mdb.get_news_item(news_id)
    if not news:
        return Response.text("Nyhet hittades inte", status=404)

    saved = request.args.get("saved", "")

    return await _render(datasette, request, "admin_news_edit.html", {
        "news": news,
        "is_new": False,
        "saved": saved,
        "author_name": _get_actor_name(request),
    })


async def admin_news_delete(scope, receive, datasette, request):
    """Delete a news item."""
    if not await _check_admin(datasette, request):
        raise Forbidden("Administratorsbehörighet krävs")

    if request.method != "POST":
        return Response.text("Method not allowed", status=405)

    mdb = _get_metadata_db()
    news_id = int(request.url_vars["news_id"])
    mdb.delete_news(news_id)
    return Response.redirect("/-/admin/news?deleted=1")
