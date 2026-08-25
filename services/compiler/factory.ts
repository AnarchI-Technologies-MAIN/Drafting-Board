import * as fs from 'fs';
import * as path from 'path';
import {
  SemanticPayload,
  AffiliateOffer,
  EngineConfig,
  CompiledPost
} from '../../types';
import { SemanticPostureEngine } from './semantics';

const BASE_DIR = path.resolve(__dirname, '../../');
const PAYLOADS_DIR = path.join(BASE_DIR, 'data', 'raw_payloads');
const DIAGRAMS_DIR = path.join(BASE_DIR, 'data', 'diagrams');
const POSTS_DIR = path.join(BASE_DIR, 'data', 'posts');
const CONFIG_FILE = path.join(BASE_DIR, 'data', 'config', 'engine_config.json');
const AFFILIATES_FILE = path.join(BASE_DIR, 'data', 'affiliates.json');
const ADS_FILE = path.join(BASE_DIR, 'data', 'ads_config.json');

if (!fs.existsSync(POSTS_DIR)) {
  fs.mkdirSync(POSTS_DIR, { recursive: true });
}

const WSRS_TRIGGER_KEYWORDS = [
  'wallet', 'smart contract', 'cryptography', 'decentralized', 'solidity',
  'web3', 'ethereum', 'evm', 'nonce', 'signature', 'private key', 'blockchain',
  'reentrancy', 'flashloan', 'defi', 'token', 'keccak', 'secp256k1'
];

export class PragmaticContentFactory {
  private affiliates: AffiliateOffer[] = [];
  private adsConfig: any = { providers: [] };
  private postureEngine = new SemanticPostureEngine();
  private config: EngineConfig = {
    dead_topics: [],
    amplified_topics: {},
    layout_modifiers: {},
    version: 1,
    last_updated: new Date().toISOString()
  };

  constructor() {
    this.loadAffiliates();
    this.loadAdsConfig();
    this.loadEngineConfig();
  }

  private loadAffiliates(): void {
    if (fs.existsSync(AFFILIATES_FILE)) {
      try {
        const raw = fs.readFileSync(AFFILIATES_FILE, 'utf-8');
        this.affiliates = JSON.parse(raw);
      } catch (err) {
        console.error('[COMPILER] Error loading affiliates.json:', err);
      }
    }
  }

  private loadAdsConfig(): void {
    if (fs.existsSync(ADS_FILE)) {
      try {
        const raw = fs.readFileSync(ADS_FILE, 'utf-8');
        this.adsConfig = JSON.parse(raw);
      } catch (err) {
        console.error('[COMPILER] Error loading ads_config.json:', err);
      }
    }
  }

  private loadEngineConfig(): void {
    if (fs.existsSync(CONFIG_FILE)) {
      try {
        const raw = fs.readFileSync(CONFIG_FILE, 'utf-8');
        this.config = JSON.parse(raw);
      } catch (err) {
        console.warn('[COMPILER] Notice: engine_config.json not found, using default.');
      }
    }
  }

  private mapAffiliates(payload: SemanticPayload, affiliateSwapFlag: boolean): AffiliateOffer[] {
    const combinedText = `${payload.title} ${payload.topic_cluster} ${payload.tech_stack.join(' ')} ${payload.cleaned_content}`.toLowerCase();
    
    const matched = this.affiliates.filter(offer => {
      return offer.keywords.some(kw => combinedText.includes(kw.toLowerCase()));
    });

    let selected = matched.length > 0 ? matched : [this.affiliates[0]];

    if (affiliateSwapFlag && selected.length > 1) {
      selected = [...selected].reverse();
    }

    return selected.slice(0, 2);
  }

  private checkWSRSRouting(payload: SemanticPayload): boolean {
    const textToScan = `${payload.title} ${payload.topic_cluster} ${payload.tech_stack.join(' ')} ${payload.cleaned_content}`.toLowerCase();
    return WSRS_TRIGGER_KEYWORDS.some(kw => textToScan.includes(kw));
  }

  private renderDiagramBlock(payload: SemanticPayload): string {
    if (!payload.linked_diagram_hash) {
      return '';
    }

    const diagramPath = path.join(DIAGRAMS_DIR, `${payload.linked_diagram_hash}.mmd`);
    let diagramContent = '';

    if (fs.existsSync(diagramPath)) {
      diagramContent = fs.readFileSync(diagramPath, 'utf-8');
    }

    return `
### 📐 System Architecture & Deterministic Workflow Schema
> [!NOTE]
> Verifiable Structural Hash Identity: \`${payload.linked_diagram_hash}\` (Deduplicated Object Store)

\`\`\`mermaid
${diagramContent || '// Diagram structure isolated via SHA-256 cryptographic indexing'}
\`\`\`
`;
  }

  /**
   * Renders WSRS Core Lead-Funnel Component with brand posture.
   */
  private renderWSRSComponent(): string {
    return `
---
### 🛡️ WALLET SAFETY REPORT SERVICE (WSRS) — VERIFIABLE EVIDENCE AUDIT
> [!WARNING]
> **Deterministic Cryptographic Security & Smart Contract Audit Alert**
>
> If your application interfaces with Web3 wallets, signature verification, or smart contract logic, unverified execution paths can lead to asset drain or private key exposure.
>
> 🔒 **Request a Deterministic WSRS Security Audit Report:**
> [👉 Request Immediate Wallet Safety Report (WSRS Audit)](https://www.anarchi-tech.com/wallet-safety-report?ref=crackback_blog_funnel)
`;
  }

  private renderScopedAdBlock(): string {
    const providers = this.adsConfig.providers || [];
    if (providers.length === 0) return '';
    const ad = providers[0];

    return `
> 📢 **${ad.badge}**: [**${ad.headline}**](${ad.target_url}) — ${ad.description} **[${ad.cta_text}](${ad.target_url})**
`;
  }

  private renderAffiliateCTABlock(offer: AffiliateOffer, rotatedLayout: boolean): string {
    if (rotatedLayout) {
      return `
> ⚡ **Deterministic Tool Recommendation**: [${offer.name}](${offer.url}) — ${offer.cta_text}. *${offer.description}*
`;
    }

    return `
┌────────────────────────────────────────────────────────────────────────┐
│ 🚀 **ANARCHI TECH VERIFIED STACK**: [**${offer.name}**](${offer.url})
│ 
│ ${offer.description}
│ 🔗 **[${offer.cta_text} →](${offer.url})**
└────────────────────────────────────────────────────────────────────────┘
`;
  }

  public compilePayload(payload: SemanticPayload): CompiledPost | null {
    const topicCluster = payload.topic_cluster || '';
    if (this.config.dead_topics.includes(topicCluster.toLowerCase())) {
      console.log(`[COMPILER] Skipping blacklisted topic cluster: ${topicCluster}`);
      return null;
    }

    const topicModifier = this.config.layout_modifiers[topicCluster] || {
      cta_layout_rotation: false,
      affiliate_mix_swap: false
    };

    const rotateCTA = topicModifier.cta_layout_rotation;
    const swapAffiliates = topicModifier.affiliate_mix_swap;
    const mappedAffiliates = this.mapAffiliates(payload, swapAffiliates);
    const needsWSRS = this.checkWSRSRouting(payload);

    const postUrl = `https://www.anarchi-tech.com/blog/${payload.slug}`;
    const jsonLdSchema = this.postureEngine.generateJSONLD(payload, postUrl);

    const dateStr = new Date().toISOString();
    let md = `---
title: "${payload.title.replace(/"/g, '\\"')}"
date: "${dateStr}"
slug: "${payload.slug}"
tech_stack: [${payload.tech_stack.map(t => `"${t}"`).join(', ')}]
topic_cluster: "${payload.topic_cluster}"
linked_diagram_hash: "${payload.linked_diagram_hash || ''}"
wsrs_routed: ${needsWSRS}
applied_layout_rotation: ${rotateCTA}
applied_affiliate_swap: ${swapAffiliates}
source: "${payload.source}"
slogan: "Deterministic software. Verifiable evidence."
json_ld_schema: ${JSON.stringify(jsonLdSchema)}
---

# ${payload.title}

> **Executive Summary**: ${payload.cleaned_summary}

`;

    md += this.renderScopedAdBlock() + '\n\n';

    if (rotateCTA && mappedAffiliates.length > 0) {
      md += this.renderAffiliateCTABlock(mappedAffiliates[0], true) + '\n\n';
    }

    const diagramSection = this.renderDiagramBlock(payload);
    if (diagramSection) {
      md += diagramSection + '\n\n';
    }

    let bodyText = payload.cleaned_content;
    if (bodyText.includes('<!-- DIAGRAM_REFERENCE_PLACEHOLDER -->')) {
      bodyText = bodyText.replace('<!-- DIAGRAM_REFERENCE_PLACEHOLDER -->', '*[Visual Architecture Diagram Extracted & Indexed Above]*');
    }
    md += `## Technical Case Study & Verifiable Evidence\n\n${bodyText}\n\n`;

    if (!rotateCTA && mappedAffiliates.length > 0) {
      md += `### Recommended Production Tooling\n`;
      mappedAffiliates.forEach(offer => {
        md += this.renderAffiliateCTABlock(offer, false) + '\n';
      });
    }

    if (needsWSRS) {
      md += this.renderWSRSComponent() + '\n';
    }

    md += `
---
*Anarchi-Technologies Dual-Engine Compiler | **Deterministic software. Verifiable evidence.** | Node: N150-HOST*
`;

    const filename = `${payload.slug}.md`;
    const filepath = path.join(POSTS_DIR, filename);
    fs.writeFileSync(filepath, md, 'utf-8');

    console.log(`[COMPILER] Compiled: ${filename} (WSRS: ${needsWSRS}, Slogan Attached)`);

    return {
      id: payload.id,
      title: payload.title,
      slug: payload.slug,
      filepath: path.relative(BASE_DIR, filepath),
      markdown: md,
      diagram_hash: payload.linked_diagram_hash,
      affiliates_injected: mappedAffiliates.map(a => a.id),
      wsrs_routed: needsWSRS,
      applied_layout_rotation: rotateCTA,
      applied_affiliate_swap: swapAffiliates,
      compiled_at: dateStr
    };
  }

  public compileAllPayloads(): CompiledPost[] {
    const results: CompiledPost[] = [];
    if (!fs.existsSync(PAYLOADS_DIR)) return results;

    const files = fs.readdirSync(PAYLOADS_DIR).filter(f => f.endsWith('.json'));
    for (const file of files) {
      const fullPath = path.join(PAYLOADS_DIR, file);
      try {
        const payload: SemanticPayload = JSON.parse(fs.readFileSync(fullPath, 'utf-8'));
        const compiled = this.compilePayload(payload);
        if (compiled) results.push(compiled);
      } catch (err) {
        console.error(`[COMPILER] Error compiling ${file}:`, err);
      }
    }
    return results;
  }
}

if (require.main === module) {
  const factory = new PragmaticContentFactory();
  const compiledPosts = factory.compileAllPayloads();
  console.log(`[COMPILER] Finished compilation. Total posts produced: ${compiledPosts.length}`);
}
