from __future__ import annotations

import random
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import connections
from django.utils import timezone

from blog.models import Post
from comments.models import Comment, PostBookmark, PostLike, PostView
from pages.models import Page
from pages.policies import POLICY_PAGES


class Command(BaseCommand):
    help = "Seed rich demo content: posts, comments, tags, categories, pages, and policy overrides."

    def add_arguments(self, parser):
        parser.add_argument("--posts", type=int, default=50, help="Number of posts to create.")
        parser.add_argument("--pages", type=int, default=5, help="Number of regular pages to create.")
        parser.add_argument("--seed", type=int, default=20260222, help="Random seed for deterministic output.")
        parser.add_argument(
            "--reset-existing",
            action="store_true",
            help="Delete existing seeded records before creating new ones.",
        )

    def handle(self, *args, **options):
        db_conn = connections["default"]
        db_name = db_conn.settings_dict.get("NAME", "")
        if db_conn.vendor != "postgresql":
            raise CommandError(
                f"seed_ultimate_content requires PostgreSQL. Active backend is '{db_conn.vendor}'."
            )
        self.stdout.write(f"Using PostgreSQL database: {db_name}")

        rnd = random.Random(options["seed"])
        now = timezone.now()

        User = get_user_model()

        author_usernames = [f"seed_author_{idx}" for idx in range(1, 7)]
        reader_usernames = [f"seed_reader_{idx}" for idx in range(1, 21)]

        authors = []
        readers = []

        for username in author_usernames:
            user, _ = User.objects.get_or_create(
                username=username,
                defaults={
                    "email": f"{username}@example.com",
                    "is_staff": True,
                },
            )
            user.set_password("Aa1357")
            user.save(update_fields=["password", "email", "is_staff"])
            authors.append(user)

        for username in reader_usernames:
            user, _ = User.objects.get_or_create(
                username=username,
                defaults={"email": f"{username}@example.com"},
            )
            user.set_password("Aa1357")
            user.save(update_fields=["password", "email"])
            readers.append(user)

        if options["reset_existing"]:
            Post.objects.filter(title__startswith="Seed Post").delete()
            Page.objects.filter(title__startswith="Seed Page").exclude(
                slug__in=[policy["slug"] for policy in POLICY_PAGES]
            ).delete()

        topics = [
            "technology",
            "engineering",
            "product",
            "design",
            "data",
            "security",
            "ai",
            "devops",
        ]
        tags = [
            "django",
            "python",
            "htmx",
            "alpinejs",
            "bootstrap",
            "performance",
            "testing",
            "seo",
            "content-strategy",
            "analytics",
            "accessibility",
            "automation",
            "postgres",
            "api-design",
            "ui-systems",
            "observability",
            "search",
            "embeddings",
        ]
        categories = [
            "technology/django",
            "technology/django/performance",
            "technology/django/performance/caching",
            "technology/django/performance/caching/redis",
            "technology/django/performance/caching/redis/production",
            "technology/frontend",
            "technology/frontend/htmx",
            "technology/frontend/alpine",
            "technology/frontend/design-systems",
            "technology/backend",
            "technology/backend/apis",
            "technology/backend/apis/graphql",
            "technology/backend/apis/graphql/resolvers",
            "writing/tutorial",
            "writing/tutorial/beginner",
            "writing/tutorial/intermediate",
            "writing/deep-dive",
            "writing/deep-dive/architecture",
            "operations/devops",
            "operations/devops/observability",
            "operations/devops/observability/metrics",
        ]

        title_openers = [
            "Scaling",
            "Designing",
            "Building",
            "Modernizing",
            "Optimizing",
            "Operationalizing",
            "Shipping",
            "Mastering",
            "Securing",
            "Evolving",
        ]
        title_subjects = [
            "Django Content Platforms",
            "Editorial Pipelines",
            "HTMX User Flows",
            "SEO Metadata Strategies",
            "Tag Taxonomy Models",
            "Composable CMS Patterns",
            "AI-assisted Search",
            "Admin Workflows",
            "Page Lifecycle Management",
            "High-traffic Blog Systems",
        ]

        lorem_blocks = [
            "This section explains the architecture decisions and operational tradeoffs behind the workflow.",
            "Teams can ship faster when data models and UI patterns stay consistent across admin and frontend.",
            "A measurable content system needs taxonomy, revision history, and clear publication states.",
            "Progressive enhancement keeps interfaces fast while still supporting rich interaction patterns.",
            "SEO quality improves when metadata, canonical URLs, and updated timestamps are managed deliberately.",
            "The biggest wins come from repeatable processes rather than one-off implementation hacks.",
        ]

        created_posts = 0
        created_comments = 0
        created_pages = 0

        for idx in range(1, options["posts"] + 1):
            author = rnd.choice(authors)
            title = f"Seed Post {idx:02d}: {rnd.choice(title_openers)} {rnd.choice(title_subjects)}"
            excerpt = (
                "Seeded article focused on scalable publishing workflows, taxonomy strategy, "
                "and SEO-aware operations."
            )

            status = rnd.choices(
                [Post.Status.PUBLISHED, Post.Status.DRAFT, Post.Status.REVIEW, Post.Status.ARCHIVED],
                weights=[78, 10, 8, 4],
                k=1,
            )[0]

            post = Post(
                author=author,
                title=title,
                excerpt=excerpt,
                body_markdown=(
                    f"# {title}\n\n"
                    f"{rnd.choice(lorem_blocks)}\n\n"
                    f"## Key Implementation Notes\n\n"
                    f"- {rnd.choice(lorem_blocks)}\n"
                    f"- {rnd.choice(lorem_blocks)}\n"
                    f"- {rnd.choice(lorem_blocks)}\n"
                ),
                status=status,
                is_featured=rnd.random() < 0.28,
                is_editors_pick=rnd.random() < 0.22,
                allow_comments=True,
                allow_reactions=True,
            )
            post.primary_topic = rnd.choice(topics)
            post.save()

            post.tags.set_tag_string(",".join(sorted(set(rnd.sample(tags, rnd.randint(4, 8))))))
            post.categories.set_tag_string(",".join(sorted(set(rnd.sample(categories, rnd.randint(2, 4))))))

            created_at = now - timedelta(days=rnd.randint(20, 420), hours=rnd.randint(0, 23))
            updated_at = created_at + timedelta(days=rnd.randint(0, 18), hours=rnd.randint(0, 12))
            if updated_at > now:
                updated_at = now - timedelta(hours=rnd.randint(1, 6))

            published_at = None
            if status in {Post.Status.PUBLISHED, Post.Status.ARCHIVED}:
                published_at = created_at + timedelta(days=rnd.randint(0, 6), hours=rnd.randint(0, 10))
                if published_at > now:
                    published_at = now - timedelta(hours=rnd.randint(1, 12))

            Post.objects.filter(pk=post.pk).update(
                created_at=created_at,
                updated_at=updated_at,
                published_at=published_at,
            )
            post.refresh_from_db()

            comment_count = rnd.randint(3, 14)
            for _ in range(comment_count):
                commenter = rnd.choice(readers)
                comment = Comment.objects.create(
                    post=post,
                    author=commenter,
                    body=(
                        f"Insightful comment on {post.title.lower()}. "
                        f"{rnd.choice(lorem_blocks)}"
                    )[:300],
                    is_approved=rnd.random() < 0.9,
                )
                comment_created = post.created_at + timedelta(days=rnd.randint(0, 24), hours=rnd.randint(0, 23))
                if comment_created > now:
                    comment_created = now - timedelta(hours=rnd.randint(2, 36))
                Comment.objects.filter(pk=comment.pk).update(
                    created_at=comment_created,
                    updated_at=comment_created + timedelta(hours=rnd.randint(0, 72)),
                )
                created_comments += 1

            like_users = rnd.sample(readers, rnd.randint(2, min(14, len(readers))))
            for like_user in like_users:
                PostLike.objects.get_or_create(post=post, user=like_user)

            bookmark_users = rnd.sample(readers, rnd.randint(1, min(10, len(readers))))
            for bookmark_user in bookmark_users:
                PostBookmark.objects.get_or_create(post=post, user=bookmark_user)

            view_count = rnd.randint(30, 420)
            for view_idx in range(view_count):
                viewer = rnd.choice([*readers, None])
                viewed_at = post.created_at + timedelta(days=rnd.randint(0, 30), hours=rnd.randint(0, 23))
                if viewed_at > now:
                    viewed_at = now - timedelta(hours=rnd.randint(1, 24))
                view = PostView.objects.create(
                    post=post,
                    user=viewer,
                    session_key=f"seed-{post.id}-{view_idx}",
                )
                PostView.objects.filter(pk=view.pk).update(viewed_at=viewed_at)

            Post.objects.filter(pk=post.pk).update(views_count=view_count)
            post.record_revision(editor=author, note="Seed baseline revision")

            created_posts += 1

        for idx in range(1, options["pages"] + 1):
            author = rnd.choice(authors)
            title = f"Seed Page {idx:02d}: {rnd.choice(title_subjects)}"
            status = rnd.choices(
                [Page.Status.PUBLISHED, Page.Status.DRAFT, Page.Status.REVIEW],
                weights=[80, 12, 8],
                k=1,
            )[0]

            page = Page.objects.create(
                author=author,
                title=title,
                summary="Seeded page covering architecture, policy, and operational guidance.",
                body_markdown=(
                    f"# {title}\n\n"
                    f"{rnd.choice(lorem_blocks)}\n\n"
                    f"## Section\n\n"
                    f"{rnd.choice(lorem_blocks)}\n\n"
                    f"{rnd.choice(lorem_blocks)}"
                ),
                template_key=rnd.choice(
                    [
                        Page.TemplateKey.DEFAULT,
                        Page.TemplateKey.LANDING,
                        Page.TemplateKey.DOCUMENTATION,
                    ]
                ),
                show_in_navigation=rnd.random() < 0.35,
                nav_order=rnd.randint(5, 150),
                is_featured=rnd.random() < 0.18,
                status=status,
            )

            page_created = now - timedelta(days=rnd.randint(15, 360), hours=rnd.randint(0, 23))
            page_updated = page_created + timedelta(days=rnd.randint(0, 25), hours=rnd.randint(0, 12))
            if page_updated > now:
                page_updated = now - timedelta(hours=rnd.randint(1, 8))

            page_published = None
            if status == Page.Status.PUBLISHED:
                page_published = page_created + timedelta(days=rnd.randint(0, 4), hours=rnd.randint(0, 12))
                if page_published > now:
                    page_published = now - timedelta(hours=rnd.randint(1, 12))

            Page.objects.filter(pk=page.pk).update(
                created_at=page_created,
                updated_at=page_updated,
                published_at=page_published,
            )
            page.refresh_from_db()
            page.record_revision(editor=author, note="Seed baseline revision")
            created_pages += 1

        policy_owner = authors[0]
        policy_updates = 0
        for policy in POLICY_PAGES:
            page, _ = Page.objects.update_or_create(
                slug=policy["slug"],
                defaults={
                    "author": policy_owner,
                    "title": policy["title"],
                    "summary": policy["summary"],
                    "body_markdown": policy["body_markdown"],
                    "status": Page.Status.PUBLISHED,
                    "template_key": Page.TemplateKey.DEFAULT,
                    "show_in_navigation": False,
                    "nav_order": 500,
                    "is_featured": False,
                    "published_at": now - timedelta(days=2),
                },
            )
            page.record_revision(editor=policy_owner, note="Policy seeded or refreshed")
            policy_updates += 1

        self.stdout.write(
            self.style.SUCCESS(
                "Seed complete: "
                f"{created_posts} posts, {created_comments} comments, "
                f"{created_pages} regular pages, {policy_updates} policy pages synced."
            )
        )
