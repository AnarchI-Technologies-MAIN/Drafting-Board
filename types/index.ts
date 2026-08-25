export interface RawIssueItem {
  id: string;
  title: string;
  source: string;
  tech_stack: string[];
  raw_body: string;
  created_at: string;
}

export interface DiagramMetadata {
  hash: string;
  format: 'mermaid' | 'plantuml' | 'dot';
  file_path: string;
  stored_newly: boolean;
  content: string;
}

export interface SemanticPayload {
  id: string;
  title: string;
  slug: string;
  tech_stack: string[];
  cleaned_summary: string;
  cleaned_content: string;
  linked_diagram_hash: string | null;
  diagram_format: string | null;
  source: string;
  extracted_at: string;
}

export interface AffiliateOffer {
  id: string;
  name: string;
  category: string;
  keywords: string[];
  url: string;
  cta_text: string;
  description: string;
  badge_color: string;
  payout_score: number;
}

export interface EngineConfig {
  dead_topics: string[];
  amplified_topics: Record<string, { priority_tier: number; boost_factor: number }>;
  layout_modifiers: Record<string, { cta_layout_rotation: boolean; affiliate_mix_swap: boolean; updated_at: string }>;
  version: number;
  last_updated: string;
}

export interface TelemetryRecord {
  category_id: string;
  topic_cluster: string;
  impressions: number;
  interaction_score: number;
  link_clicks: number;
  conversions_count: number;
  affiliate_revenue: number;
  wsrs_revenue: number;
  anar_core_signups: number;
  window_start?: string;
  window_end?: string;
}

export interface CompiledPost {
  id: string;
  title: string;
  slug: string;
  filepath: string;
  markdown: string;
  diagram_hash: string | null;
  affiliates_injected: string[];
  wsrs_routed: boolean;
  applied_layout_rotation: boolean;
  applied_affiliate_swap: boolean;
  compiled_at: string;
}
