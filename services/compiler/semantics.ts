/**
 * SERVICES / COMPILER / SEMANTICS.TS
 * Machine-Enforced Semantic Posture & Metadata Engine
 *
 * Brand Identity: "Deterministic software. Verifiable evidence."
 * Generates Schema.org JSON-LD microdata, OpenGraph posture metadata,
 * W3C HTML5 semantic landmarks, and accessibility tags for Anarchi-Tech.
 */

import { CompiledPost, SemanticPayload } from '../../types';

export interface SemanticPosture {
  jsonLdSchema: string;
  metaTags: string;
  semanticArticleWrapper: (bodyHtml: string) => string;
}

export class SemanticPostureEngine {
  /**
   * Generates Schema.org TechArticle JSON-LD microdata with Anarchi-Tech brand posture.
   */
  public generateJSONLD(payload: SemanticPayload | any, postUrl: string): string {
    const schema = {
      "@context": "https://schema.org",
      "@type": "TechArticle",
      "headline": payload.title,
      "description": payload.cleaned_summary,
      "mainEntityOfPage": {
        "@type": "WebPage",
        "@id": postUrl
      },
      "author": {
        "@type": "Organization",
        "name": "Anarchi-Technologies",
        "url": "https://www.anarchi-tech.com",
        "slogan": "Deterministic software. Verifiable evidence."
      },
      "publisher": {
        "@type": "Organization",
        "name": "Anarchi-Technologies",
        "url": "https://www.anarchi-tech.com",
        "slogan": "Deterministic software. Verifiable evidence.",
        "logo": {
          "@type": "ImageObject",
          "url": "https://www.anarchi-tech.com/assets/logo.png"
        }
      },
      "datePublished": payload.extracted_at || new Date().toISOString(),
      "dateModified": new Date().toISOString(),
      "keywords": (payload.tech_stack || []).join(", "),
      "articleSection": payload.topic_cluster || "Deterministic Engineering",
      "proficiencyLevel": "Expert"
    };

    return JSON.stringify(schema, null, 2);
  }

  /**
   * Generates OpenGraph and Twitter Card metadata tags.
   */
  public generateMetaTags(title: string, summary: string, slug: string, techStack: string[]): string {
    const canonicalUrl = `https://www.anarchi-tech.com/blog/${slug}`;
    const keywordsStr = techStack.join(', ');

    return `
    <!-- Machine-Enforced Semantic Posture Meta Tags -->
    <!-- Brand Slogan: Deterministic software. Verifiable evidence. -->
    <meta name="description" content="${summary.replace(/"/g, '&quot;')} | Deterministic software. Verifiable evidence.">
    <meta name="keywords" content="${keywordsStr}">
    <link rel="canonical" href="${canonicalUrl}">

    <!-- OpenGraph Metadata -->
    <meta property="og:site_name" content="Anarchi-Technologies | Deterministic Software. Verifiable Evidence.">
    <meta property="og:title" content="${title.replace(/"/g, '&quot;')}">
    <meta property="og:description" content="${summary.replace(/"/g, '&quot;')}">
    <meta property="og:type" content="article">
    <meta property="og:url" content="${canonicalUrl}">
    <meta property="og:image" content="https://www.anarchi-tech.com/assets/og-cover.png">

    <!-- Twitter Card Metadata -->
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:site" content="@anarchi_tech">
    <meta name="twitter:title" content="${title.replace(/"/g, '&quot;')}">
    <meta name="twitter:description" content="${summary.replace(/"/g, '&quot;')}">
    `;
  }
}
