from __future__ import annotations

from datetime import date

POLICY_PAGES = [
    {
        "slug": "privacy-policy",
        "title": "Privacy Policy",
        "summary": "How we collect, use, and protect personal information across the platform.",
        "updated_at": date(2026, 2, 22),
        "body_markdown": """
## Overview

This Privacy Policy explains how Ultimate Blog collects and processes information when you browse, create an account, publish content, or interact with platform features.

## Information We Collect

- **Account information**: username, email address, profile data.
- **Content information**: posts, comments, reactions, page content, and revision history.
- **Technical information**: IP address, session identifiers, browser metadata, and access logs.
- **Usage information**: page views, feature interactions, and aggregated analytics.

## How We Use Information

We use collected data to:

- operate and secure the service,
- personalize content and moderation workflows,
- prevent abuse and enforce platform rules,
- improve product reliability, performance, and UX,
- satisfy legal obligations.

## Data Sharing

We do not sell personal data. Information may be shared with trusted service providers strictly for infrastructure, security, and operations support under contractual controls.

## Data Retention

We retain data only as long as required for platform operation, legal compliance, and dispute resolution. Data may be anonymized for analytics.

## Your Rights

Depending on jurisdiction, you may request access, correction, export, restriction, or deletion of your personal data.

## Security

We apply technical and organizational safeguards, but no online system can be guaranteed 100 percent secure.

## Contact

For privacy requests, contact the platform administrator.
""".strip(),
    },
    {
        "slug": "terms-of-service",
        "title": "Terms of Service",
        "summary": "Rules and legal terms governing use of the platform and services.",
        "updated_at": date(2026, 2, 22),
        "body_markdown": """
## Acceptance of Terms

By using Ultimate Blog, you agree to these Terms of Service and applicable laws.

## Use of the Service

You agree to use the platform lawfully and responsibly. You must not attempt to disrupt, exploit, or misuse system resources.

## Accounts

You are responsible for maintaining account credentials and all activities under your account.

## User Content

You retain ownership of your content. By posting, you grant the platform permission to display, process, and store content to operate the service.

## Prohibited Conduct

You may not publish unlawful, malicious, infringing, or abusive content, including spam, malware, or deceptive material.

## Moderation and Enforcement

The platform may remove content, suspend accounts, or restrict access when policy violations are detected.

## Availability

Service availability is provided on an as-is basis and may change, pause, or terminate without prior notice.

## Liability

To the fullest extent permitted by law, the platform is not liable for indirect or consequential damages resulting from use of the service.

## Changes to Terms

We may update these terms. Continued use after updates constitutes acceptance of the revised terms.
""".strip(),
    },
    {
        "slug": "cookie-policy",
        "title": "Cookie Policy",
        "summary": "How cookies and similar technologies are used for sessions, analytics, and performance.",
        "updated_at": date(2026, 2, 22),
        "body_markdown": """
## What Are Cookies

Cookies are small text files stored on your device by your browser.

## How We Use Cookies

We use cookies and similar technologies for:

- session management and authentication,
- security controls,
- performance diagnostics,
- feature and preference continuity.

## Cookie Categories

- **Essential cookies**: required for core platform operation.
- **Analytics cookies**: aggregate usage insights for performance improvements.
- **Preference cookies**: retain user interface and workflow preferences.

## Managing Cookies

You can control cookies through browser settings. Disabling essential cookies may break authentication or core functionality.

## Updates

This policy may be updated when cookie usage patterns or legal requirements change.
""".strip(),
    },
    {
        "slug": "disclaimer",
        "title": "Disclaimer",
        "summary": "Important limitations regarding accuracy, availability, and professional advice.",
        "updated_at": date(2026, 2, 22),
        "body_markdown": """
## Informational Use

Content on Ultimate Blog is provided for informational and educational purposes only.

## No Professional Advice

Content is not legal, financial, medical, or other regulated professional advice.

## Accuracy

We attempt to keep content current and accurate, but we do not guarantee completeness, reliability, or suitability for every use case.

## External Links

Links to third-party websites are provided for convenience and do not imply endorsement.

## Risk and Responsibility

You are responsible for decisions made based on platform content. Use content at your own discretion.
""".strip(),
    },
    {
        "slug": "community-guidelines",
        "title": "Community Guidelines",
        "summary": "Behavior and content standards for constructive publishing and discussion.",
        "updated_at": date(2026, 2, 22),
        "body_markdown": """
## Core Principles

Our community values clarity, respect, and evidence-driven discussion.

## Expected Behavior

- engage constructively,
- challenge ideas without personal attacks,
- provide sources when making technical claims,
- avoid spam and low-quality repetitive posting.

## Not Allowed

- harassment, hate, threats, or doxxing,
- malware, phishing, and fraud,
- copyright abuse,
- automated abuse and manipulation.

## Moderation Actions

Moderators may edit visibility, remove content, freeze threads, or suspend accounts for policy violations.

## Reporting

If you see harmful or policy-violating content, report it to moderators or administrators.
""".strip(),
    },
]

POLICY_MAP = {policy["slug"]: policy for policy in POLICY_PAGES}
POLICY_SLUGS = [policy["slug"] for policy in POLICY_PAGES]
