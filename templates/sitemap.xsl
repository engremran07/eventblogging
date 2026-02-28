<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0"
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:sitemap="http://www.sitemaps.org/schemas/sitemap/0.9">

  <xsl:output method="html" encoding="UTF-8" indent="yes"/>

  <xsl:template match="/">
    <html lang="en">
      <head>
        <meta charset="utf-8"/>
        <title>Ultimate Blog Sitemap</title>
        <style>
          :root {
            --bg: #f6f8fb;
            --panel: #ffffff;
            --text: #1f2a37;
            --muted: #61738a;
            --line: #dde6ef;
            --brand: #1273de;
            --brand-soft: #e8f2ff;
          }
          * { box-sizing: border-box; }
          body {
            margin: 0;
            font-family: "Space Grotesk", "Segoe UI", sans-serif;
            color: var(--text);
            background: radial-gradient(circle at 0% 0%, #e5f0ff 0%, var(--bg) 45%);
          }
          .wrap {
            max-width: 1080px;
            margin: 32px auto;
            padding: 0 20px;
          }
          .hero {
            background: linear-gradient(125deg, #0c3f73, #1273de);
            color: #fff;
            border-radius: 16px;
            padding: 26px;
            box-shadow: 0 12px 28px rgba(18, 115, 222, 0.24);
            margin-bottom: 16px;
          }
          .hero h1 { margin: 0 0 8px 0; font-size: 28px; }
          .hero p { margin: 0; opacity: 0.94; }
          .panel {
            background: var(--panel);
            border: 1px solid var(--line);
            border-radius: 16px;
            overflow: hidden;
            box-shadow: 0 8px 26px rgba(17, 24, 39, 0.08);
          }
          table {
            width: 100%;
            border-collapse: collapse;
            table-layout: fixed;
          }
          th, td {
            border-bottom: 1px solid var(--line);
            padding: 12px 14px;
            text-align: left;
            vertical-align: top;
            word-break: break-word;
          }
          th {
            background: #f8fbff;
            color: #123a63;
            font-size: 12px;
            letter-spacing: 0.06em;
            text-transform: uppercase;
          }
          tr:hover td { background: #fbfdff; }
          a { color: var(--brand); text-decoration: none; }
          a:hover { text-decoration: underline; }
          .muted { color: var(--muted); }
          .pill {
            display: inline-block;
            padding: 4px 8px;
            border-radius: 999px;
            font-size: 12px;
            background: var(--brand-soft);
            color: #124f92;
          }
          .meta { margin-top: 12px; color: var(--muted); font-size: 13px; }
          .top-actions { margin-top: 10px; }
          .top-actions a {
            display: inline-block;
            margin-right: 10px;
            padding: 6px 10px;
            border-radius: 8px;
            background: rgba(255, 255, 255, 0.14);
            color: #fff;
          }
          .top-actions a:hover { background: rgba(255, 255, 255, 0.24); text-decoration: none; }
        </style>
      </head>
      <body>
        <div class="wrap">
          <div class="hero">
            <h1>Ultimate Blog Sitemap</h1>
            <p>Structured XML sitemap for bots, rendered with XSL for humans.</p>
            <div class="top-actions">
              <a href="/">Home</a>
              <a href="/pages/policies/">Policies</a>
              <a href="/sitemap.xml">Sitemap Index</a>
            </div>
          </div>

          <xsl:choose>
            <xsl:when test="sitemap:sitemapindex">
              <div class="panel">
                <table>
                  <thead>
                    <tr>
                      <th style="width: 72%;">Sitemap</th>
                      <th style="width: 28%;">Last Modified</th>
                    </tr>
                  </thead>
                  <tbody>
                    <xsl:for-each select="sitemap:sitemapindex/sitemap:sitemap">
                      <tr>
                        <td>
                          <a>
                            <xsl:attribute name="href"><xsl:value-of select="sitemap:loc"/></xsl:attribute>
                            <xsl:value-of select="sitemap:loc"/>
                          </a>
                        </td>
                        <td><span class="muted"><xsl:value-of select="sitemap:lastmod"/></span></td>
                      </tr>
                    </xsl:for-each>
                  </tbody>
                </table>
              </div>
              <div class="meta">
                <span class="pill">Index</span>
                <span>Contains multiple sitemap sections for scalable crawling.</span>
              </div>
            </xsl:when>

            <xsl:otherwise>
              <div class="panel">
                <table>
                  <thead>
                    <tr>
                      <th style="width: 62%;">URL</th>
                      <th style="width: 18%;">Last Modified</th>
                      <th style="width: 10%;">Priority</th>
                      <th style="width: 10%;">Change Freq</th>
                    </tr>
                  </thead>
                  <tbody>
                    <xsl:for-each select="sitemap:urlset/sitemap:url">
                      <tr>
                        <td>
                          <a>
                            <xsl:attribute name="href"><xsl:value-of select="sitemap:loc"/></xsl:attribute>
                            <xsl:value-of select="sitemap:loc"/>
                          </a>
                        </td>
                        <td><span class="muted"><xsl:value-of select="sitemap:lastmod"/></span></td>
                        <td><span class="muted"><xsl:value-of select="sitemap:priority"/></span></td>
                        <td><span class="muted"><xsl:value-of select="sitemap:changefreq"/></span></td>
                      </tr>
                    </xsl:for-each>
                  </tbody>
                </table>
              </div>
              <div class="meta">
                <span class="pill">URL Set</span>
                <span>Optimized for search crawlers and readable for reviewers.</span>
              </div>
            </xsl:otherwise>
          </xsl:choose>
        </div>
      </body>
    </html>
  </xsl:template>
</xsl:stylesheet>
