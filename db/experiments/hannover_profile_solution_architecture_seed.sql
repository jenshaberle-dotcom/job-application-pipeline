-- POC-ONLY / NOT A DEPLOYMENT MIGRATION
-- Additional acquisition vocabulary for Solution Architecture.
-- Opt-in execution only; this file is intentionally outside db/migrations/.
-- Never creates/reconfigures market sensors, connector sources or schedules.
-- Never changes previously active search terms.
-- Newly staged terms stay inactive pending deliberate operator review.
WITH target_profiles(profile_name) AS (
    VALUES
        ('ba_data_engineer_30629_50km'),
        ('ba_data_engineering_remote_nationwide_review'),
        ('stepstone_data_engineer_hannover')
),
terms(search_term) AS (
    VALUES
        ('Solution Architect'),
        ('Solutions Architect'),
        ('Lösungsarchitekt'),
        ('IT-Lösungsarchitekt'),
        ('IT Solution Architect'),
        ('AI Solution Architect'),
        ('Cloud Solution Architect'),
        ('Integration Architect'),
        ('IT-Architekt'),
        ('Anwendungsarchitekt'),
        ('Softwarearchitekt'),
        ('Enterprise Architect'),
        ('Technical Architect')
)
INSERT INTO search_terms (search_profile_id, search_term, is_active)
SELECT sp.id, terms.search_term, FALSE
FROM search_profiles sp
JOIN target_profiles target ON target.profile_name = sp.profile_name
CROSS JOIN terms
ON CONFLICT (search_profile_id, search_term) DO NOTHING;
