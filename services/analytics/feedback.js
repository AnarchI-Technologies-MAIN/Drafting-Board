/**
 * SERVICES / ANALYTICS / FEEDBACK.JS
 * Pillar 3: Revenue-Weighted Telemetry Optimization Engine (JavaScript)
 *
 * Automatically calculates, adjusts, and re-orders system content generation parameters
 * based on performance telemetry and financial revenue conversion feedback.
 */

const fs = require('fs');
const path = require('path');

const BASE_DIR = path.resolve(__dirname, '../../');
const CONFIG_FILE = path.join(BASE_DIR, 'data', 'config', 'engine_config.json');
const TELEMETRY_FILE = path.join(BASE_DIR, 'data', 'config', 'telemetry_sample.json');

/**
 * Loads current engine configuration or provides default defaults.
 */
function loadConfig() {
  if (fs.existsSync(CONFIG_FILE)) {
    try {
      const raw = fs.readFileSync(CONFIG_FILE, 'utf-8');
      return JSON.parse(raw);
    } catch (err) {
      console.error('[FEEDBACK] Error reading config file, initializing fresh:', err.message);
    }
  }

  return {
    dead_topics: [],
    amplified_topics: {},
    layout_modifiers: {},
    version: 1,
    last_updated: new Date().toISOString()
  };
}

/**
 * Saves updated engine configuration file.
 */
function saveConfig(config) {
  const dir = path.dirname(CONFIG_FILE);
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }

  config.version = (config.version || 1) + 1;
  config.last_updated = new Date().toISOString();

  fs.writeFileSync(CONFIG_FILE, JSON.stringify(config, null, 2), 'utf-8');
  console.log(`[FEEDBACK] Engine configuration updated and saved to: ${CONFIG_FILE}`);
}

/**
 * Main analytical feedback evaluator function.
 * @param {Array<Object>|Object} telemetryInput Raw telemetry records array or consolidated object.
 */
function processTelemetryFeedback(telemetryInput) {
  const config = loadConfig();
  const records = Array.isArray(telemetryInput) ? telemetryInput : [telemetryInput];

  console.log(`\n===============================================================`);
  console.log(`[FEEDBACK] Evaluating Telemetry Matrix for ${records.length} cluster record(s)...`);
  console.log(`===============================================================\n`);

  let rulesTriggered = {
    dropped: [],
    amplified: [],
    rewritten: []
  };

  records.forEach(record => {
    const topic = (record.topic_cluster || record.category_id || 'general').toLowerCase();
    const impressions = Number(record.impressions || 0);
    const affiliateRev = Number(record.affiliate_revenue || 0);
    const wsrsRev = Number(record.wsrs_revenue || 0);
    const totalRevenue = affiliateRev + wsrsRev;
    const clicks = Number(record.link_clicks || 0);
    const signups = Number(record.anar_core_signups || 0);
    const ctr = impressions > 0 ? (clicks / impressions) : 0;
    const conversionRate = impressions > 0 ? ((record.conversions_count || 0) / impressions) : 0;

    console.log(`📈 Cluster: '${topic}' | Impressions: ${impressions} | Revenue: $${totalRevenue.toFixed(2)} | Clicks: ${clicks} | CTR: ${(ctr*100).toFixed(1)}% | Signups: ${signups}`);

    // ------------------------------------------------------------------------
    // RULE 1 (DROP):
    // If impressions > 500 but direct service/affiliate revenue == $0.00
    // Write cluster string to dead_topics and drop permanently.
    // ------------------------------------------------------------------------
    if (impressions > 500 && totalRevenue === 0) {
      if (!config.dead_topics.includes(topic)) {
        config.dead_topics.push(topic);
      }
      // Clean up amplified or modifier records if present
      delete config.amplified_topics[topic];
      delete config.layout_modifiers[topic];

      rulesTriggered.dropped.push(topic);
      console.log(` ❌ [RULE 1 TRIGGERED - DROP] Permanently blacklisted dead topic: '${topic}' (>500 impr, $0.00 rev)`);
      return; // Stop further processing for dead topic
    }

    // ------------------------------------------------------------------------
    // RULE 2 (AMPLIFY):
    // High conversion coefficients or accelerated Anar-Core signups
    // Automatically promote ingestion priority tier to scale out production.
    // ------------------------------------------------------------------------
    if (totalRevenue >= 50.00 || signups >= 2 || (impressions > 0 && conversionRate > 0.03)) {
      const currentTier = (config.amplified_topics[topic] && config.amplified_topics[topic].priority_tier) || 1;
      const newTier = Math.min(currentTier + 1, 5); // Tier 1 -> Tier 5 max

      config.amplified_topics[topic] = {
        priority_tier: newTier,
        boost_factor: Number((1.5 * newTier).toFixed(1)),
        updated_at: new Date().toISOString()
      };

      rulesTriggered.amplified.push({ topic, tier: newTier });
      console.log(` 🚀 [RULE 2 TRIGGERED - AMPLIFY] Promoted priority tier for '${topic}' to Tier ${newTier} (Rev: $${totalRevenue.toFixed(2)}, Signups: ${signups})`);
    }

    // ------------------------------------------------------------------------
    // RULE 3 (REWRITE):
    // Significant traffic loops (>200 impressions) but weak monetization (revenue < $10.00 or CTR < 2%)
    // Append layout modifier flags instructing compiler to rotate CTA positions or swap affiliate mix.
    // ------------------------------------------------------------------------
    if (impressions >= 200 && (totalRevenue < 10.00 || ctr < 0.02) && !config.dead_topics.includes(topic)) {
      const currentModifier = config.layout_modifiers[topic] || { cta_layout_rotation: false, affiliate_mix_swap: false };
      
      // Toggle rotation / swap states for next cycle
      const updatedModifier = {
        cta_layout_rotation: true,
        affiliate_mix_swap: !currentModifier.affiliate_mix_swap,
        updated_at: new Date().toISOString()
      };

      config.layout_modifiers[topic] = updatedModifier;

      rulesTriggered.rewritten.push({ topic, modifier: updatedModifier });
      console.log(` 🔄 [RULE 3 TRIGGERED - REWRITE] Layout modifier applied to '${topic}' (CTA Rotation: true, Affiliate Swap: ${updatedModifier.affiliate_mix_swap})`);
    }
  });

  saveConfig(config);
  return {
    status: 'success',
    config,
    rulesTriggered
  };
}

// CLI execution helper
if (require.main === module) {
  let telemetryData = [];
  if (fs.existsSync(TELEMETRY_FILE)) {
    try {
      telemetryData = JSON.parse(fs.readFileSync(TELEMETRY_FILE, 'utf-8'));
    } catch (e) {
      console.error('[FEEDBACK] Error reading telemetry_sample.json:', e);
    }
  } else {
    // Default fallback telemetry sample for demonstration
    telemetryData = [
      {
        category_id: "cat_solidity_security",
        topic_cluster: "solidity-reentrancy",
        impressions: 850,
        interaction_score: 92,
        link_clicks: 64,
        conversions_count: 5,
        affiliate_revenue: 250.00,
        wsrs_revenue: 450.00,
        anar_core_signups: 4
      },
      {
        category_id: "cat_legacy_php",
        topic_cluster: "php-deprecated-arrays",
        impressions: 620,
        interaction_score: 15,
        link_clicks: 2,
        conversions_count: 0,
        affiliate_revenue: 0.00,
        wsrs_revenue: 0.00,
        anar_core_signups: 0
      },
      {
        category_id: "cat_react_state",
        topic_cluster: "react-useeffect-loop",
        impressions: 340,
        interaction_score: 45,
        link_clicks: 3,
        conversions_count: 1,
        affiliate_revenue: 5.00,
        wsrs_revenue: 0.00,
        anar_core_signups: 0
      }
    ];
  }

  processTelemetryFeedback(telemetryData);
}

module.exports = {
  processTelemetryFeedback,
  loadConfig,
  saveConfig
};
